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

    def status(self) -> dict:
        with self._lock:
            selected_id = self._selected_id
            loaded = self._silero is not None
            load_error = self._silero_error
            verified = self._silero_verified

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
            else:
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
    def close(self) -> None:
        with self._lock:
            self._silero = None
            self._silero_verified = False

