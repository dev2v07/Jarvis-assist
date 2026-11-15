"""DAW discovery plus a bounded, confirmation-first control surface.

The service never accepts an arbitrary command line. It only resolves known DAW
executables and exposes a small allow-list of actions. Project inspection stays
read-only; launching a detected DAW requires an explicit confirmation flag.
"""

from __future__ import annotations

import json
import hashlib
import math
import os
import subprocess
import wave
from pathlib import Path

from services.bible_paths import resolve, runtime_path


class DawControlService:
    def __init__(self, backend_dir: Path) -> None:
        root = Path(backend_dir).parent
        self.audit_path = resolve(backend_dir, "data/knowledge3/environment_audit.json")
        self.registry_path = resolve(backend_dir, "data/knowledge3/audio/plugin_registry.json")
        self.snapshot_root = runtime_path(Path(backend_dir), "daw", "snapshots")

    def _read(self, path: Path, fallback):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return fallback

    def summary(self) -> dict:
        audit = self._read(self.audit_path, {})
        programs = audit.get("installed_programs", []) if isinstance(audit, dict) else []
        names = [str(row.get("name", row)) if isinstance(row, dict) else str(row) for row in programs]
        daws = [name for name in names if any(token in name.lower() for token in ("cubase", "reaper", "nuendo"))]
        return {
            "daws": daws,
            "detected": bool(daws),
            "control_mode": "read_only_discovery",
            "supported_actions": ["list_detected", "inspect_plugins", "open_documentation", "inspect_project", "launch"],
            "automation_status": "confirmation_first",
            "read_only_project_inspection": True,
        }

    def plugin_inventory(self, query: str = "", limit: int = 250) -> dict:
        """Return a read-only inventory of plugin binaries on audited paths.

        Presence on disk is deliberately not reported as "loaded" or
        "compatible": loading a plugin in Cubase/REAPER needs a DAW-side
        probe.  The inventory is still useful to the knowledge search and
        keeps that distinction explicit for callers.
        """
        registry = self._read(self.registry_path, {})
        configured = registry.get("plugin_paths", {}) if isinstance(registry, dict) else {}
        needle = str(query or "").strip().lower()
        rows: list[dict] = []
        seen: set[str] = set()
        extensions = {
            "vst2": {".dll"},
            "vst3": {".vst3"},
        }
        for plugin_format, entries in extensions.items():
            for item in configured.get(plugin_format, []) if isinstance(configured, dict) else []:
                if not isinstance(item, dict) or not item.get("exists"):
                    continue
                root = Path(str(item.get("path", "")))
                if not root.is_dir():
                    continue
                try:
                    candidates = root.rglob("*")
                    for candidate in candidates:
                        if not candidate.is_file() or candidate.suffix.lower() not in entries:
                            continue
                        key = str(candidate.resolve()).lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        if needle and needle not in candidate.name.lower():
                            continue
                        stat = candidate.stat()
                        rows.append({
                            "name": candidate.stem,
                            "path": str(candidate),
                            "format": plugin_format,
                            "size": stat.st_size,
                            "mtime_ns": stat.st_mtime_ns,
                            "status": "present_on_disk",
                            "loaded_in_daw": "not_tested",
                        })
                except (OSError, PermissionError):
                    continue
        rows.sort(key=lambda row: (row["format"], row["name"].lower(), row["path"].lower()))
        bounded_limit = max(1, min(int(limit or 250), 1000))
        return {
            "read_only": True,
            "query": query,
            "plugins": rows[:bounded_limit],
            "count": len(rows),
            "returned": min(len(rows), bounded_limit),
            "truncated": len(rows) > bounded_limit,
            "loaded_in_daw": False,
            "note": "Наличие файла не подтверждает загрузку или совместимость в DAW.",
        }

    def search(self, query: str = "") -> list[dict]:
        value = str(query or "").strip().lower()
        summary = self.summary()
        return [{"name": name, "kind": "daw", "status": "detected"} for name in summary["daws"] if not value or value in name.lower()]

    def _known_executable(self, daw: str) -> Path | None:
        """Resolve Cubase/REAPER only from audited or fixed vendor locations."""
        needle = str(daw or "").lower()
        audit = self._read(self.audit_path, {})
        programs = audit.get("installed_programs", []) if isinstance(audit, dict) else []
        candidates: list[Path] = []
        for row in programs:
            if not isinstance(row, dict) or needle not in str(row.get("name", "")).lower():
                continue
            location = str(row.get("install_location", "")).strip().strip('"')
            if location:
                root = Path(location)
                candidates.extend(root.glob("*.exe") if root.exists() else [])
                candidates.extend(root.rglob("*.exe") if root.exists() else [])
        if "cubase" in needle:
            candidates.extend(Path("C:/Program Files/Steinberg").glob("Cubase*/Cubase*.exe"))
        if "reaper" in needle:
            candidates.extend([Path(r"C:\Program Files\REAPER (x64)\reaper.exe"), Path(r"C:\Program Files\REAPER\reaper.exe")])
        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate).lower()
            if key in seen:
                continue
            seen.add(key)
            if candidate.is_file() and candidate.suffix.lower() == ".exe":
                return candidate
        return None

    def plan_action(self, action: str, daw: str = "", project_path: str = "") -> dict:
        """Return a validated action plan without changing the workstation."""
        normalized = str(action or "").strip().lower()
        allowed = {"open_documentation", "inspect_project", "launch"}
        if normalized not in allowed:
            raise ValueError(f"Недопустимое действие DAW: {action}")
        if normalized == "open_documentation":
            url = "https://www.steinberg.help/" if "cubase" in daw.lower() else "https://www.reaper.fm/userguide.php"
            return {"action": normalized, "daw": daw, "url": url, "requires_confirmation": False, "executable": None}
        if normalized == "inspect_project":
            if not project_path:
                raise ValueError("Для inspect_project нужен project_path")
            inspected = self.inspect_project(project_path)
            return {"action": normalized, "daw": daw, "requires_confirmation": False, "executable": None, "project": inspected}
        executable = self._known_executable(daw)
        return {
            "action": normalized,
            "daw": daw,
            "requires_confirmation": True,
            "available": executable is not None,
            "executable": str(executable) if executable else None,
            "argv": [str(executable)] if executable else [],
        }

    def execute_action(self, action: str, daw: str = "", project_path: str = "", confirmed: bool = False) -> dict:
        plan = self.plan_action(action, daw, project_path)
        if action.strip().lower() != "launch":
            return {"executed": False, "plan": plan}
        if not plan.get("available"):
            return {"executed": False, "plan": plan, "error": "DAW не найден среди разрешённых установок"}
        if not confirmed:
            return {"executed": False, "plan": plan, "error": "Требуется явное подтверждение запуска"}
        executable = str(plan["executable"])
        subprocess.Popen([executable], cwd=str(Path(executable).parent), close_fds=True)
        return {"executed": True, "plan": plan}

    def inspect_project(self, project_path: str) -> dict:
        path = Path(project_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(str(path))
        if not path.is_dir():
            raise ValueError("project_path должен быть папкой проекта")
        files = [item for item in path.rglob("*") if item.is_file()]
        extensions: dict[str, int] = {}
        track_candidates: list[str] = []
        track_analysis: list[dict] = []
        for item in files:
            ext = item.suffix.lower() or "[no_extension]"
            extensions[ext] = extensions.get(ext, 0) + 1
            if ext in {".wav", ".flac", ".mp3", ".aiff", ".aif", ".mid", ".midi"}:
                track_candidates.append(str(item.relative_to(path)))
                track_analysis.append(self._analyze_media(item, path))
        cubase_projects = [str(item.relative_to(path)) for item in files if item.suffix.lower() == ".cpr"]
        return {
            "path": str(path),
            "read_only": True,
            "files": len(files),
            "extensions": dict(sorted(extensions.items())),
            "cubase_projects": cubase_projects,
            "media_candidates": track_candidates[:500],
            "media_candidates_truncated": len(track_candidates) > 500,
            "track_analysis": track_analysis[:500],
            "track_analysis_truncated": len(track_analysis) > 500,
            "routing": {
                "available": False,
                "read_only": True,
                "note": "Cubase CPR routing and plugin state require a supported project adapter; no project files were modified.",
            },
            "actions": {
                "can_read_structure": True,
                "can_modify_project": False,
                "requires_confirmation_for_changes": True,
            },
        }

    def project_report(self, project_path: str) -> dict:
        """Build a bounded, read-only DAW report from the inspected project.

        This intentionally summarizes discoverable media only.  Cubase CPR
        routing, plugin state and automation are not inferred from filenames;
        they remain explicit adapter gaps instead of guessed values.
        """
        inspected = self.inspect_project(project_path)
        tracks = inspected.get("track_analysis", [])
        role_counts: dict[str, int] = {}
        audio_files = 0
        total_duration = 0.0
        clipping_files = 0
        peak_values: list[float] = []
        rms_values: list[float] = []
        for track in tracks:
            role = str(track.get("role_guess", "unknown"))
            role_counts[role] = role_counts.get(role, 0) + 1
            metadata = track.get("audio_metadata")
            if not isinstance(metadata, dict):
                continue
            audio_files += 1
            total_duration += float(metadata.get("duration", 0.0) or 0.0)
            if metadata.get("clipping"):
                clipping_files += 1
            for target, bucket in (("peak_dbfs", peak_values), ("rms_dbfs", rms_values)):
                value = metadata.get(target)
                if isinstance(value, (int, float)):
                    bucket.append(float(value))
        return {
            "path": inspected["path"],
            "read_only": True,
            "project_files": inspected["files"],
            "cubase_projects": inspected["cubase_projects"],
            "media_candidates": len(inspected["media_candidates"]),
            "audio_files_decoded": audio_files,
            "total_audio_duration_seconds": round(total_duration, 3),
            "role_counts": dict(sorted(role_counts.items())),
            "levels": {
                "peak_dbfs_max": round(max(peak_values), 2) if peak_values else None,
                "rms_dbfs_max": round(max(rms_values), 2) if rms_values else None,
                "clipping_files": clipping_files,
            },
            "routing": {
                "status": "unavailable",
                "reason": "Требуется отдельный безопасный Cubase CPR adapter; маршрутизация не угадывается по media-файлам.",
            },
            "plugin_state": {
                "status": "unavailable",
                "reason": "Состояние VST внутри CPR не читается этим read-only сканером.",
            },
            "automation": {
                "status": "not_inspected",
                "reason": "Изменение и интерпретация automation требуют подтвержденного DAW adapter.",
            },
            "control": {
                "status": "confirmation_adapter_required",
                "can_modify_project": False,
                "undo_available": False,
            },
            "snapshots": self._snapshots_for_project(inspected["path"]),
        }

    def _snapshots_for_project(self, project_path: str) -> list[dict]:
        snapshots: list[dict] = []
        for manifest_path in sorted(self.snapshot_root.glob("*.json")):
            payload = self._read(manifest_path, {})
            if str(payload.get("project_path", "")) != str(project_path):
                continue
            snapshots.append({
                "name": payload.get("snapshot_name", manifest_path.stem),
                "path": str(manifest_path),
                "status": payload.get("status", "CREATED"),
                "files": len(payload.get("files", [])),
                "restore_available": bool(payload.get("restore", {}).get("available", False)),
            })
        return snapshots

    def snapshot_project(self, project_path: str, snapshot_name: str, confirmed: bool = False) -> dict:
        """Create a non-destructive manifest checkpoint outside the project."""
        path = Path(project_path).expanduser().resolve()
        if not path.is_dir():
            raise FileNotFoundError(str(path))
        safe_name = "".join(char if char.isalnum() or char in "-_" else "_" for char in str(snapshot_name or "checkpoint"))
        safe_name = safe_name.strip("._")[:80] or "checkpoint"
        files = [item for item in path.rglob("*") if item.is_file()]
        manifest = {
            "version": 1,
            "read_only_source": True,
            "confirmed": bool(confirmed),
            "project_path": str(path),
            "snapshot_name": safe_name,
            "files": [],
            "restore": {
                "available": False,
                "requires_confirmed_adapter": True,
                "note": "Это контрольная точка manifest; исходные файлы не копируются и не изменяются.",
            },
        }
        if not confirmed:
            manifest["planned_files"] = len(files)
            manifest["status"] = "CONFIRMATION_REQUIRED"
            return manifest
        for item in files:
            digest = hashlib.sha256()
            with item.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            stat = item.stat()
            manifest["files"].append({
                "path": str(item.relative_to(path)),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "sha256": digest.hexdigest(),
            })
        destination = self.snapshot_root / f"{safe_name}.json"
        if destination.exists():
            raise FileExistsError(f"Контрольная точка уже существует: {destination.name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest["status"] = "CREATED"
        manifest["manifest_path"] = str(destination)
        return manifest

    @staticmethod
    def _analyze_media(item: Path, project_root: Path) -> dict:
        """Return bounded metadata and a conservative role guess for one media file."""
        relative = str(item.relative_to(project_root))
        stem = item.stem.lower().replace("_", " ").replace("-", " ")
        role_tokens = {
            "vocals": ("vocal", "vox", "voice", "lead"),
            "drums": ("drum", "kick", "snare", "tom", "hihat", "hat"),
            "bass": ("bass", "sub"),
            "guitar": ("guitar", "gtr", "riff", "solo"),
            "keys": ("piano", "keys", "synth", "pad"),
            "fx": ("fx", "effect", "amb", "noise"),
        }
        role = "unknown"
        for candidate, tokens in role_tokens.items():
            if any(token in stem.split() for token in tokens):
                role = candidate
                break
        result = {"path": relative, "kind": item.suffix.lower().lstrip("."), "role_guess": role}
        if item.suffix.lower() not in {".wav", ".wave"}:
            result["audio_metadata"] = "not_decoded_in_safe_project_scan"
            return result
        try:
            with wave.open(str(item), "rb") as source:
                frames = source.readframes(source.getnframes())
                width = source.getsampwidth()
                channels = source.getnchannels()
                rate = source.getframerate()
            if not frames or width not in (1, 2, 3, 4):
                result["audio_error"] = "empty_or_unsupported_wav"
                return result
            values = []
            maximum = 0
            squares = 0.0
            full_scale = float(2 ** (width * 8 - 1))
            for offset in range(0, len(frames) - width + 1, width):
                sample = int.from_bytes(frames[offset:offset + width], "little", signed=True)
                maximum = max(maximum, abs(sample))
                squares += float(sample * sample)
                values.append(sample)
            count = max(1, len(values))
            peak_ratio = maximum / full_scale
            rms_ratio = math.sqrt(squares / count) / full_scale
            result["audio_metadata"] = {
                "samplerate": rate,
                "channels": channels,
                "duration": round(len(frames) / max(width * channels * rate, 1), 3),
                "peak_dbfs": round(20 * math.log10(max(peak_ratio, 1e-12)), 2),
                "rms_dbfs": round(20 * math.log10(max(rms_ratio, 1e-12)), 2),
                "clipping": maximum >= int(full_scale),
            }
        except (OSError, ValueError, wave.Error) as error:
            result["audio_error"] = str(error)[:240]
        return result
