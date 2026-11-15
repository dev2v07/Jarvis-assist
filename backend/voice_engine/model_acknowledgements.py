"""Pre-generated Fish Audio acknowledgements used before an Ollama turn."""

from __future__ import annotations

from pathlib import Path


MODEL_ACKNOWLEDGEMENTS: tuple[tuple[str, str], ...] = (
    ("Сейчас подумаю.", "model_ack_01.wav"),
    ("Уточняю информацию.", "model_ack_02.wav"),
    ("Изучаю Ваш вопрос, сэр.", "model_ack_03.wav"),
    ("Изучаю Ваш запрос.", "model_ack_04.wav"),
    ("Сейчас просканирую.", "model_ack_05.wav"),
    ("Сканирую глобальную сеть.", "model_ack_06.wav"),
    ("Я в поисках ответа, сэр.", "model_ack_07.wav"),
)


def model_acknowledgement_dir(project_root: Path) -> Path:
    """Return the canonical Bible audio directory for model acknowledgements."""

    return Path(project_root) / "data" / "Bible" / "audio" / "voice_responses" / "model_ack"


def model_acknowledgement_catalog() -> tuple[dict[str, str], ...]:
    return tuple({"text": text, "wav": wav} for text, wav in MODEL_ACKNOWLEDGEMENTS)
