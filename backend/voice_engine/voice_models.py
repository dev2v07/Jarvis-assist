"""Voice-model registry and lazy inference adapters.

The registry deliberately separates the selected profile from the engine that
actually produces audio.  Jarvis remains the product-default profile while
its current XTTS implementation is treated as a temporary fallback until the
trained Jarvis model is available.
"""

from __future__ import annotations

import importlib.util
import os
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


def _environment_value(name: str, default: str = "") -> str:
    """Read process env and, on Windows, the current user env as a fallback.

    The desktop app can be started from a long-lived shell whose environment
    predates a `setx`/profile change. Reading HKCU here keeps voice settings
    consistent without logging or copying the secret elsewhere.
    """
    value = str(os.getenv(name, "") or "").strip()
    if value:
        return value
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
                value, _ = winreg.QueryValueEx(key, name)
                return str(value or "").strip()
        except (FileNotFoundError, OSError):
            pass
    return default


@dataclass(frozen=True)
class VoiceModelSpec:
    model_id: str
    name: str
    description: str
    status: str
    default: bool = False
    engine: str = ""


MODEL_SPECS = (
    VoiceModelSpec(
        model_id="jarvis",
        name="Jarvis",
        description="Основная голосовая модель",
        status="В разработке",
        default=False,
        engine="xtts_v2_fallback",
    ),
    VoiceModelSpec(
        model_id="fish_jarvis",
        name="Fish Audio — Джарвис",
        description="Облачный голосовой профиль Fish Audio",
        status="Рабочий профиль Fish Audio",
        default=True,
        engine="fish_audio_s2_1_pro_free",
    ),
    VoiceModelSpec(
        model_id="fish_dean",
        name="Fish Audio — Дин Винчестер",
        description="Отдельный облачный голосовой профиль Fish Audio",
        status="Ожидает отдельный API-ключ и voice ID",
        engine="fish_audio_s2_1_pro_free",
    ),
)


class VoiceModelManager:
    """Own lazy-loaded model instances and expose factual health information."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self._selected_id = "fish_jarvis"
        self._fish_error: dict[str, str] = {}
        self._fish_verified: dict[str, bool] = {}
        self._lock = threading.RLock()

    @property
    def selected_id(self) -> str:
        with self._lock:
            return self._selected_id

    def select(self, model_id: str) -> dict:
        model_id = str(model_id or "").strip().lower()
        if model_id not in {spec.model_id for spec in MODEL_SPECS}:
            raise ValueError(f"Неизвестная голосовая модель: {model_id}")
        with self._lock:
            self._selected_id = model_id
        return self.status()

    def _fish_config(self, profile: str = "jarvis") -> tuple[str, str, str]:
        suffix = "_DEAN" if profile == "dean" else ""
        return (
            _environment_value(f"FISH_AUDIO{suffix}_API_KEY"),
            _environment_value(
                f"FISH_AUDIO{suffix}_REFERENCE_ID",
                "3fc339d7c6474b11a221708e2a7b1c4b" if profile == "jarvis" else "",
            ),
            _environment_value(f"FISH_AUDIO{suffix}_MODEL", "s2.1-pro-free") or "s2.1-pro-free",
        )

    def _fish_availability(self, profile: str = "jarvis") -> tuple[bool, str]:
        api_key, reference_id, _ = self._fish_config(profile)
        suffix = "_DEAN" if profile == "dean" else ""
        if not api_key:
            return False, f"Не задана переменная FISH_AUDIO{suffix}_API_KEY"
        if not reference_id:
            return False, f"Не задан FISH_AUDIO{suffix}_REFERENCE_ID"
        if importlib.util.find_spec("requests") is None:
            return False, "Зависимость requests не установлена"
        return True, ""

    def status(self) -> dict:
        with self._lock:
            selected_id = self._selected_id
            fish_verified = dict(self._fish_verified)
            fish_error = dict(self._fish_error)

        models = []
        for spec in MODEL_SPECS:
            item = asdict(spec)
            if spec.model_id == "jarvis":
                item.update(
                    ready=False,
                    available=True,
                    actual_engine="xtts_v2_fallback",
                    message=(
                        "Обученная модель Jarvis ещё не установлена; "
                        "для ответов используется существующий XTTS v2 fallback."
                    ),
                )
            else:
                profile = "dean" if spec.model_id == "fish_dean" else "jarvis"
                fish_ready, fish_config_error = self._fish_availability(profile)
                profile_verified = fish_verified.get(profile, False)
                profile_error = fish_error.get(profile, "")
                item.update(
                    ready=fish_ready and profile_verified,
                    available=fish_ready,
                    loaded=profile_verified,
                    inference_verified=profile_verified,
                    actual_engine="fish_audio_s2_1_pro_free" if fish_ready else "",
                    message=(
                        "Fish Audio API проверен в текущем процессе"
                        if profile_verified
                        else profile_error
                        or ("API-ключ найден; первый синтез проверит доступность Fish Audio" if fish_ready else "")
                        or fish_config_error
                        or "Fish Audio недоступен"
                    ),
                )
            item["selected"] = spec.model_id == selected_id
            models.append(item)

        selected = next(item for item in models if item["selected"])
        return {
            "selected_id": selected_id,
            "selected": selected,
            "models": models,
        }

    def synthesize_fish(self, text: str, profile: str = "jarvis") -> bytes:
        """Generate WAV bytes through the Fish Audio cloud API."""
        api_key, reference_id, model = self._fish_config(profile)
        ready, error = self._fish_availability(profile)
        if not ready:
            with self._lock:
                self._fish_error[profile] = error
            raise RuntimeError(error)
        try:
            import requests

            try:
                fish_timeout = max(5, min(90, int(os.getenv("JARVIS_FISH_TTS_TIMEOUT", "20"))))
            except (TypeError, ValueError):
                fish_timeout = 20

            response = requests.post(
                "https://api.fish.audio/v1/tts",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "model": model,
                },
                json={
                    "text": str(text),
                    "reference_id": reference_id,
                    "format": "wav",
                },
                # Keep a provider outage from blocking the voice worker for
                # the general LLM timeout. The selected Fish profile remains
                # authoritative; this is only a bounded failure window.
                timeout=(8, fish_timeout),
            )
            response.raise_for_status()
            if not response.content:
                raise RuntimeError("Fish Audio вернул пустой WAV")
            with self._lock:
                self._fish_verified[profile] = True
                self._fish_error[profile] = ""
            return response.content
        except Exception as error:
            with self._lock:
                self._fish_error[profile] = str(error)
                # A previous successful inference must not keep the profile
                # advertised as ready after the current request failed.
                # The selected profile remains Fish; this only makes health
                # status factual until the next successful inference.
                self._fish_verified[profile] = False
            raise RuntimeError(f"Fish Audio synthesis failed: {error}") from error

    def close(self) -> None:
        with self._lock:
            self._fish_verified.clear()
            self._fish_error.clear()

