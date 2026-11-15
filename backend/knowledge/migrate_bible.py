"""Stage the physical Knowledge roots into the canonical Bible tree.

This command is intentionally copy-only.  It never edits or removes source
files.  The generated manifest is the evidence needed before a later runtime
cutover.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


SOURCE_ROOTS = {
    "offline_knowledge": Path("data/offline_knowledge"),
    "knowledge3": Path("data/knowledge3"),
    "voice_responses": Path("data/voice_responses"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def target_for(source_name: str, relative: Path, digest: str) -> Path:
    suffix = relative.suffix.lower()
    if suffix == ".wav":
        if source_name == "voice_responses":
            return Path("data/Bible/audio") / "responses" / relative
        return Path("data/Bible/audio") / "library" / source_name / relative
    return Path("data/Bible/sources") / source_name / relative


def stage(root: Path, *, verify_only: bool = False) -> dict:
    bible_root = root / "data" / "Bible"
    records: list[dict] = []
    by_hash: dict[str, str] = {}
    missing: list[str] = []
    copied = 0
    deduplicated = 0

    for source_name, relative_root in SOURCE_ROOTS.items():
        source_root = root / relative_root
        if not source_root.is_dir():
            missing.append(str(relative_root).replace("\\", "/"))
            continue
        for source in sorted(path for path in source_root.rglob("*") if path.is_file()):
            relative = source.relative_to(root).as_posix()
            digest = sha256(source)
            target_relative = target_for(source_name, source.relative_to(source_root), digest).as_posix()
            existing = by_hash.get(digest)
            if existing:
                target_relative = existing
                deduplicated += 1
            else:
                by_hash[digest] = target_relative
                if not verify_only:
                    target = root / target_relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    copied += 1
            records.append({
                "source": relative,
                "canonical": target_relative,
                "sha256": digest,
                "size": source.stat().st_size,
            })

    if not verify_only:
        manifest = {
            "version": 1,
            "status": "STAGED_VERIFIED",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "copy_only": True,
            "originals_preserved": True,
            "source_roots": {key: path.as_posix() for key, path in SOURCE_ROOTS.items()},
            "records": records,
            "summary": {
                "source_files": len(records),
                "canonical_files": len(by_hash),
                "copied": copied,
                "deduplicated_by_sha256": deduplicated,
                "missing_roots": missing,
            },
        }
        output = bible_root / "index" / "physical_manifest.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "source_files": len(records),
        "canonical_files": len(by_hash),
        "copied": copied,
        "deduplicated_by_sha256": deduplicated,
        "missing_roots": missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(stage(args.root.resolve(), verify_only=args.verify_only), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
