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
        default=True,
        engine="xtts_v2_fallback",
    ),
    VoiceModelSpec(
        model_id="kesha",
        name="Kesha",
        description="Временный голосовой профиль на базе стандартного Silero ru_v3 (диктор aidar)",
        status="Проверяется локальный Silero checkpoint",
        engine="silero_ru_v3_aidar",
    ),
    VoiceModelSpec(
        model_id="fish_jarvis",
        name="Fish Audio — Джарвис",
        description="Облачный голосовой профиль Fish Audio",
        status="Проверяется API Fish Audio",
        engine="fish_audio_s2_1_pro_free",
    ),
)


class VoiceModelManager:
    """Own lazy-loaded model instances and expose factual health information."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.silero_checkpoint = (
            self.base_dir / "voice_engine" / "models" / "silero" / "ru_v3.pt"
        )
        self._selected_id = "jarvis"
        self._silero: Any | None = None
        self._silero_error = ""
        self._silero_verified = False
        self._fish_error = ""
        self._fish_verified = False
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

    def _kesha_availability(self) -> tuple[bool, str]:
        if not self.silero_checkpoint.is_file():
            return False, f"Checkpoint не найден: {self.silero_checkpoint}"
        if importlib.util.find_spec("torch") is None:
            return False, "Зависимость torch не установлена"
        try:
            import torch  # noqa: F401
        except Exception as error:  # pragma: no cover - environment-specific
            return False, f"Не удалось загрузить torch: {error}"
        return True, ""

    def _fish_config(self) -> tuple[str, str, str]:
        return (
            str(os.getenv("FISH_AUDIO_API_KEY", "")).strip(),
            str(os.getenv("FISH_AUDIO_REFERENCE_ID", "3fc339d7c6474b11a221708e2a7b1c4b")).strip(),
            str(os.getenv("FISH_AUDIO_MODEL", "s2.1-pro-free")).strip() or "s2.1-pro-free",
        )

    def _fish_availability(self) -> tuple[bool, str]:
        api_key, reference_id, _ = self._fish_config()
        if not api_key:
            return False, "Не задана переменная FISH_AUDIO_API_KEY"
        if not reference_id:
            return False, "Не задан FISH_AUDIO_REFERENCE_ID"
        if importlib.util.find_spec("requests") is None:
            return False, "Зависимость requests не установлена"
        return True, ""

    def status(self) -> dict:
        with self._lock:
            selected_id = self._selected_id
            loaded = self._silero is not None
            load_error = self._silero_error
            verified = self._silero_verified
            fish_verified = self._fish_verified
            fish_error = self._fish_error

        kesha_ready, kesha_error = self._kesha_availability()
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
            elif spec.model_id == "kesha":
                item.update(
                    ready=kesha_ready and verified,
                    available=kesha_ready,
                    loaded=loaded,
                    inference_verified=verified,
                    actual_engine="silero_ru_v3_aidar" if kesha_ready else "",
                    message=(
                        "Silero-инференс проверен в текущем процессе"
                        if verified
                        else "Локальный checkpoint доступен; инференс будет проверен при первом синтезе"
                        if kesha_ready
                        else kesha_error or load_error or "Модель недоступна"
                    ),
                )
            else:
                fish_ready, fish_config_error = self._fish_availability()
                item.update(
                    ready=fish_ready and fish_verified,
                    available=fish_ready,
                    loaded=fish_verified,
                    inference_verified=fish_verified,
                    actual_engine="fish_audio_s2_1_pro_free" if fish_ready else "",
                    message=(
                        "Fish Audio API проверен в текущем процессе"
                        if fish_verified
                        else "API-ключ найден; первый синтез проверит доступность Fish Audio"
                        if fish_ready
                        else fish_config_error or fish_error or "Fish Audio недоступен"
                    ),
                )
            item["selected"] = spec.model_id == selected_id
            models.append(item)

        selected = next(item for item in models if item["selected"])
        return {
            "selected_id": selected_id,
            "selected": selected,
            "models": models,
            "silero_checkpoint": str(self.silero_checkpoint),
            "silero_checkpoint_exists": self.silero_checkpoint.is_file(),
        }

    def _load_kesha(self):
        with self._lock:
            if self._silero is not None:
                return self._silero
            ready, error = self._kesha_availability()
            if not ready:
                self._silero_error = error
                raise RuntimeError(error)
            try:
                import torch

                importer = torch.package.PackageImporter(str(self.silero_checkpoint))
                model = importer.load_pickle("tts_models", "model")
                # Silero's packaged multi-speaker wrapper is not an nn.Module;
                # its apply_tts implementation already runs inference-only.
                eval_method = getattr(model, "eval", None)
                if callable(eval_method):
                    eval_method()
                self._silero = model
                self._silero_error = ""
                return model
            except Exception as error:
                self._silero_error = str(error)
                raise RuntimeError(f"Не удалось загрузить Silero Kesha: {error}") from error

    def synthesize_kesha(self, text: str):
        """Return a CPU tensor and sample rate using the source project's recipe."""
        model = self._load_kesha()
        sample_rate = int(os.getenv("JARVIS_KESHA_SAMPLE_RATE", "24000"))
        if sample_rate not in (8000, 24000, 48000):
            sample_rate = 24000
        try:
            audio = model.apply_tts(
                text=str(text),
                speaker="aidar",
                sample_rate=sample_rate,
                put_accent=True,
                put_yo=True,
            )
            with self._lock:
                self._silero_verified = True
            return audio, sample_rate
        except Exception as error:
            with self._lock:
                self._silero_error = str(error)
            raise RuntimeError(f"Silero synthesis failed: {error}") from error

    def synthesize_fish(self, text: str) -> bytes:
        """Generate WAV bytes through the Fish Audio cloud API."""
        api_key, reference_id, model = self._fish_config()
        ready, error = self._fish_availability()
        if not ready:
            with self._lock:
                self._fish_error = error
            raise RuntimeError(error)
        try:
            import requests

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
                timeout=(10, 90),
            )
            response.raise_for_status()
            if not response.content:
                raise RuntimeError("Fish Audio вернул пустой WAV")
            with self._lock:
                self._fish_verified = True
                self._fish_error = ""
            return response.content
        except Exception as error:
            with self._lock:
                self._fish_error = str(error)
            raise RuntimeError(f"Fish Audio synthesis failed: {error}") from error

    def close(self) -> None:
        with self._lock:
            self._silero = None
            self._silero_verified = False
            self._fish_verified = False

