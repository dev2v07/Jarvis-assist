from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def inspect(path: Path) -> dict:
    result = {"path": str(path), "exists": path.exists(), "size": path.stat().st_size if path.exists() else 0, "tables": []}
    if not path.exists():
        return result
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        names = connection.execute("select name from sqlite_master where type='table' order by name").fetchall()
        for (name,) in names:
            columns = connection.execute(f"pragma table_info([{name}])").fetchall()
            rows = connection.execute(f"select count(*) from [{name}]").fetchone()[0]
            result["tables"].append({"name": name, "columns": columns, "rows": rows})
    finally:
        connection.close()
    return result


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    paths = (
        root / "backend/data/jarvis_state.sqlite3",
        root / "backend/data/jarvis.sqlite3",
        root / "backend/data/account_system/account_state.sqlite3",
        root / "data/filesystem_index.db",
    )
    print(json.dumps([inspect(path) for path in paths], ensure_ascii=False, indent=2))
