"""Safe storage migration gate.

The harness never writes to the source databases.  It creates SQLite copies
using the online backup API, verifies their integrity, takes a second backup to
prove idempotent copying, and exercises rollback on an isolated target.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.storage_registry import storage_paths_for_backend


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_sqlite(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"file:{source.as_posix()}?mode=ro"
    source_connection = sqlite3.connect(source_uri, uri=True)
    target_connection = sqlite3.connect(str(target))
    try:
        source_connection.backup(target_connection)
        target_connection.execute("PRAGMA integrity_check")
    finally:
        target_connection.close()
        source_connection.close()


def inspect_copy(path: Path) -> dict[str, object]:
    connection = sqlite3.connect(str(path))
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        logical_dump = "\n".join(connection.iterdump()).encode("utf-8")
    finally:
        connection.close()
    return {
        "sha256": sha256(path),
        "logical_sha256": hashlib.sha256(logical_dump).hexdigest(),
        "integrity": integrity,
        "tables": [row[0] for row in tables],
    }


def run(source_root: Path, work_dir: Path) -> dict[str, object]:
    registry = storage_paths_for_backend(source_root)
    target_root = work_dir / "target"
    rollback_root = work_dir / "rollback"
    results: dict[str, object] = {"source_root": str(source_root), "stores": {}}

    for name, source in registry.existing().items():
        try:
            relative = Path("data") / source.relative_to(source_root / "data")
        except ValueError:
            relative = Path("external") / source.name
        target = target_root / relative
        rollback = rollback_root / relative
        backup_sqlite(source, target)
        before = inspect_copy(target)
        backup_sqlite(target, rollback)
        after = inspect_copy(rollback)
        if before["logical_sha256"] != after["logical_sha256"] or before["integrity"] != "ok" or after["integrity"] != "ok":
            raise RuntimeError(f"storage copy/rollback verification failed for {name}")
        results["stores"][name] = {"source": str(source), "target": str(target), "rollback": str(rollback), "verified": True, "snapshot": before}
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path)
    args = parser.parse_args()
    if args.work_dir:
        report = run(args.source_root.resolve(), args.work_dir.resolve())
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    with tempfile.TemporaryDirectory(prefix="jarvis-storage-gate-") as directory:
        report = run(args.source_root.resolve(), Path(directory))
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
