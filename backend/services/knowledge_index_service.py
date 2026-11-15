"""Read-only access to the shared Knowledge 3.0 index."""

from __future__ import annotations

import json
from pathlib import Path

from services.bible_paths import resolve, runtime_path


class KnowledgeIndexService:
    def __init__(self, backend_dir: Path) -> None:
        self.backend_dir = Path(backend_dir)
        self.project_root = Path(backend_dir).parent
        self.bible_root = self.project_root / "data" / "Bible"
        self._physical_map = self._load_physical_map()
        self.index_path = self._canonical_path("data/knowledge3/index.json")

    def _load_physical_map(self) -> dict[str, Path]:
        manifest_path = self.bible_root / "index" / "physical_manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}
        if not manifest.get("records"):
            return {}
        return {
            str(item.get("source")): self.project_root / str(item.get("canonical"))
            for item in manifest.get("records", [])
            if item.get("source") and item.get("canonical")
        }

    def _canonical_path(self, source_path: str) -> Path:
        return resolve(self.backend_dir, source_path)

    def read(self) -> dict:
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {"version": 1, "read_only": True, "modules": [], "error": "index_unavailable"}

    def summary(self) -> dict:
        index = self.read()
        return {
            "version": index.get("version", 1),
            "read_only": bool(index.get("read_only", True)),
            "modules": index.get("modules", []),
            "offline_knowledge": index.get("offline_knowledge", {}),
            "environment": index.get("environment", {}),
            "music": index.get("music", {}),
            "programming": index.get("programming", {}),
            "audio": index.get("audio", {}),
            "voice": index.get("voice", {}),
            "guitar": index.get("guitar", {}),
            "psychology": index.get("psychology", {}),
            "literature": index.get("literature", {}),
            "daw": index.get("daw", {}),
            "mixing": index.get("mixing", {}),
            "error": index.get("error"),
        }

    def integrity(self) -> dict:
        root = self.project_root
        source_root = self.bible_root / ".internal" / "sources"
        if not source_root.is_dir():
            source_root = self.bible_root / "sources"
        if not source_root.is_dir():
            source_root = self.bible_root / "materials"
        knowledge3 = source_root / "knowledge3"
        offline_root = source_root / "offline_knowledge"
        voice = source_root / "voice_responses"
        errors: list[str] = []
        warnings: list[str] = []
        if len({knowledge3.resolve(), offline_root.resolve(), voice.resolve()}) != 3:
            errors.append("physical knowledge roots are not separate")
        seen: dict[str, str] = {}
        index = self.read()
        module_roots_checked = 0
        for module in index.get("modules", []):
            module_id = str(module.get("id", ""))
            if module_id in seen:
                errors.append(f"duplicate module id: {module_id}")
            seen[module_id] = str(module.get("storage", ""))
            storage = str(module.get("storage", "")).strip()
            if not storage:
                errors.append(f"module has no storage: {module_id}")
                continue
            module_root = self._canonical_path(storage)
            module_roots_checked += 1
            if not module_root.is_dir():
                errors.append(f"module storage missing: {module_id}: {storage}")
        catalog_paths_checked = 0
        for key, value in index.items():
            if not isinstance(value, dict):
                continue
            path_value = value.get("path")
            if not path_value or key in {"environment"}:
                continue
            catalog_path = Path(str(path_value))
            if not catalog_path.is_absolute():
                catalog_path = self._canonical_path(str(catalog_path).replace("\\", "/"))
            catalog_paths_checked += 1
            if not catalog_path.is_file():
                errors.append(f"index catalog missing: {key}: {path_value}")
        audio_records = 0
        audio_ready = 0
        for path in (
            knowledge3 / "voice" / "lessons.json",
            knowledge3 / "audio" / "lessons.json",
            knowledge3 / "programming" / "lessons.json",
        ):
            try:
                rows = json.loads(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
                errors.append(f"cannot read {path.name}: {exc}")
                continue
            for row in rows if isinstance(rows, list) else []:
                audio_records += 1
                if row.get("audio_status") == "AUDIO_READY":
                    audio_ready += 1
                    audio_path = Path(str(row.get("audio_path", "")))
                    if not audio_path.is_absolute():
                        audio_path = self._canonical_path(str(audio_path).replace("\\", "/"))
                    try:
                        if not audio_path.is_file() or audio_path.stat().st_size <= 44:
                            errors.append(f"AUDIO_READY points to missing/empty file: {row.get('id')}")
                    except OSError as exc:
                        errors.append(f"cannot stat audio for {row.get('id')}: {exc}")
        guitar_records = 0
        guitar_ready = 0
        guitar_catalog = knowledge3 / "guitar" / "catalog.json"
        try:
            guitar_payload = json.loads(guitar_catalog.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read guitar catalog: {exc}")
            guitar_payload = {"models": []}
        for row in guitar_payload.get("models", []) if isinstance(guitar_payload, dict) else []:
            guitar_records += 1
            if row.get("audio_status") != "AUDIO_READY":
                continue
            guitar_ready += 1
            audio_path = Path(str(row.get("audio_path", "")))
            if not audio_path.is_absolute():
                audio_path = self._canonical_path(str(audio_path).replace("\\", "/"))
            try:
                if not audio_path.is_file() or audio_path.stat().st_size <= 44:
                    errors.append(f"guitar AUDIO_READY points to missing/empty file: {row.get('id')}")
            except OSError as exc:
                errors.append(f"cannot stat guitar audio for {row.get('id')}: {exc}")
        literature_records = 0
        literature_ready = 0
        literature_catalog = knowledge3 / "literature" / "catalog.json"
        try:
            literature_payload = json.loads(literature_catalog.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read literature catalog: {exc}")
            literature_payload = {"works": []}
        for row in literature_payload.get("works", []) if isinstance(literature_payload, dict) else []:
            literature_records += 1
            if row.get("audio_status") != "AUDIO_READY":
                continue
            literature_ready += 1
            audio_path = Path(str(row.get("audio_path", "")))
            if not audio_path.is_absolute():
                audio_path = self._canonical_path(str(audio_path).replace("\\", "/"))
            try:
                if not audio_path.is_file() or audio_path.stat().st_size <= 44:
                    errors.append(f"literature AUDIO_READY points to missing/empty file: {row.get('id')}")
            except OSError as exc:
                errors.append(f"cannot stat literature audio for {row.get('id')}: {exc}")
        psychology_records = 0
        psychology_ready = 0
        psychology_catalog = knowledge3 / "psychology" / "cards.json"
        try:
            psychology_payload = json.loads(psychology_catalog.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read psychology catalog: {exc}")
            psychology_payload = {"cards": []}
        for row in psychology_payload.get("cards", []) if isinstance(psychology_payload, dict) else []:
            psychology_records += 1
            if row.get("audio_status") != "AUDIO_READY":
                continue
            psychology_ready += 1
            audio_path = Path(str(row.get("audio_path", "")))
            if not audio_path.is_absolute():
                audio_path = self._canonical_path(str(audio_path).replace("\\", "/"))
            try:
                if not audio_path.is_file() or audio_path.stat().st_size <= 44:
                    errors.append(f"psychology AUDIO_READY points to missing/empty file: {row.get('id')}")
            except OSError as exc:
                errors.append(f"cannot stat psychology audio for {row.get('id')}: {exc}")
        card_audio_counts: dict[str, tuple[int, int]] = {}
        for module_name in ("mixing", "daw"):
            records = 0
            ready = 0
            catalog = knowledge3 / module_name / "catalog.json"
            try:
                payload = json.loads(catalog.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
                errors.append(f"cannot read {module_name} catalog: {exc}")
                payload = {"cards": []}
            for row in payload.get("cards", []) if isinstance(payload, dict) else []:
                records += 1
                if row.get("audio_status") != "AUDIO_READY":
                    continue
                ready += 1
                audio_path = Path(str(row.get("audio_path", "")))
                if not audio_path.is_absolute():
                    audio_path = self._canonical_path(str(audio_path).replace("\\", "/"))
                try:
                    if not audio_path.is_file() or audio_path.stat().st_size <= 44:
                        errors.append(f"{module_name} AUDIO_READY points to missing/empty file: {row.get('id')}")
                except OSError as exc:
                    errors.append(f"cannot stat {module_name} audio for {row.get('id')}: {exc}")
            card_audio_counts[module_name] = (records, ready)
        offline_records = 0
        offline_ready = 0
        offline_catalog = offline_root / "catalog.json"
        try:
            offline_payload = json.loads(offline_catalog.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read offline knowledge catalog: {exc}")
            offline_payload = {"topics": []}
        for topic in offline_payload.get("topics", []) if isinstance(offline_payload, dict) else []:
            if topic.get("status") == "VERIFIED" and topic.get("review_status") != "USER_CONFIRMED":
                warnings.append(f"verified offline topic lacks explicit review confirmation: {topic.get('id')}")
            for item in topic.get("audio", []):
                offline_records += 1
                if str(item.get("status", "")).lower() != "ready":
                    continue
                offline_ready += 1
                audio_path = Path(str(item.get("path", "")))
                if not audio_path.is_absolute():
                    audio_path = self._canonical_path(str(audio_path).replace("\\", "/"))
                try:
                    if not audio_path.is_file() or audio_path.stat().st_size <= 44:
                        errors.append(f"offline ready audio points to missing/empty file: {topic.get('id')}:{item.get('variant')}")
                except OSError as exc:
                    errors.append(f"cannot stat offline audio for {topic.get('id')}:{item.get('variant')}: {exc}")
        snapshot_root = runtime_path(self.backend_dir, "daw", "snapshots")
        legacy_snapshot_root = knowledge3 / "daw" / "snapshots"
        snapshot_records = 0
        snapshot_roots = [snapshot_root]
        if legacy_snapshot_root.is_dir() and legacy_snapshot_root != snapshot_root:
            snapshot_roots.append(legacy_snapshot_root)
        for current_root in snapshot_roots:
            if not current_root.is_dir():
                continue
            for snapshot_path in current_root.glob("*.json"):
                snapshot_records += 1
                try:
                    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
                    if not snapshot.get("read_only_source") or not isinstance(snapshot.get("files"), list):
                        errors.append(f"invalid DAW snapshot manifest: {snapshot_path.name}")
                except (OSError, json.JSONDecodeError) as exc:
                    errors.append(f"cannot read DAW snapshot {snapshot_path.name}: {exc}")
        if not errors and audio_ready == 0:
            warnings.append("no Knowledge 3.0 lesson has verified audio yet")
        audio_groups = {
            "lessons": (audio_records, audio_ready),
            "guitar": (guitar_records, guitar_ready),
            "literature": (literature_records, literature_ready),
            "psychology": (psychology_records, psychology_ready),
            "mixing": card_audio_counts.get("mixing", (0, 0)),
            "daw": card_audio_counts.get("daw", (0, 0)),
            "offline": (offline_records, offline_ready),
        }

        def readiness(records: int, ready: int) -> str:
            if records <= 0:
                return "NOT_DISCOVERED"
            if ready >= records:
                return "AUDIO_READY"
            if ready > 0:
                return "AUDIO_PARTIAL"
            return "AUDIO_PENDING"

        audio_group_status = {
            name: {
                "records": records,
                "ready": ready,
                "status": readiness(records, ready),
            }
            for name, (records, ready) in audio_groups.items()
        }
        overall_status = "ERROR" if errors else (
            "READY"
            if all(item["status"] in {"AUDIO_READY", "NOT_DISCOVERED"} for item in audio_group_status.values())
            else "PARTIAL"
        )
        # `ok` is a readiness contract for callers, not merely a structural
        # parse/error flag.  A library with partially prepared audio must not
        # be reported as fully ready to the UI or acceptance checks.
        return {
            "ok": overall_status == "READY",
            "ready": overall_status == "READY",
            "status": overall_status,
            "errors": errors,
            "warnings": warnings,
            "audio_groups": audio_group_status,
            "roots": {"knowledge3": str(knowledge3), "offline_knowledge": str(offline_root), "voice_responses": str(voice)},
            "module_roots_checked": module_roots_checked,
            "catalog_paths_checked": catalog_paths_checked,
            "lesson_audio_records": audio_records,
            "lesson_audio_ready": audio_ready,
            "guitar_audio_records": guitar_records,
            "guitar_audio_ready": guitar_ready,
            "literature_audio_records": literature_records,
            "literature_audio_ready": literature_ready,
            "psychology_audio_records": psychology_records,
            "psychology_audio_ready": psychology_ready,
            "mixing_audio_records": card_audio_counts.get("mixing", (0, 0))[0],
            "mixing_audio_ready": card_audio_counts.get("mixing", (0, 0))[1],
            "daw_audio_records": card_audio_counts.get("daw", (0, 0))[0],
            "daw_audio_ready": card_audio_counts.get("daw", (0, 0))[1],
            "offline_audio_records": offline_records,
            "offline_audio_ready": offline_ready,
            "daw_snapshot_manifests": snapshot_records,
        }
