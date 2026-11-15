"""Rewrite copied JSON references to canonical Bible file paths only."""

from __future__ import annotations

import json
from pathlib import Path


def rewrite(root: Path) -> dict[str, int]:
    manifest_path = root / "data" / "Bible" / "index" / "physical_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mapping = {
        str(item["source"]).replace("\\", "/"): str(item["canonical"]).replace("\\", "/")
        for item in manifest.get("records", [])
    }
    changed_files = 0
    changed_refs = 0

    def transform(value):
        nonlocal changed_refs
        if isinstance(value, dict):
            return {key: transform(item) for key, item in value.items()}
        if isinstance(value, list):
            return [transform(item) for item in value]
        if isinstance(value, str):
            replacement = mapping.get(value.replace("\\", "/"))
            if replacement and replacement != value:
                changed_refs += 1
                return replacement
        return value

    for path in sorted((root / "data" / "Bible" / "materials").rglob("*.json")):
        original = json.loads(path.read_text(encoding="utf-8"))
        updated = transform(original)
        if updated != original:
            path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed_files += 1
    return {"changed_files": changed_files, "changed_references": changed_refs}


if __name__ == "__main__":
    print(rewrite(Path(__file__).resolve().parents[2]))
