"""Read-only audio metering for the Mixing & Mastering Engineer MVP."""

from __future__ import annotations

import math
import subprocess
import uuid
import wave
from pathlib import Path

from services.bible_paths import runtime_path

try:
    import numpy as np
except ImportError:  # pragma: no cover - optional analysis enhancement
    np = None

try:
    from scipy import signal as scipy_signal
except ImportError:  # pragma: no cover - optional loudness enhancement
    scipy_signal = None


class MixingService:
    def render_preview(self, audio_path: str, preset: str = "clean_headroom", confirmed: bool = False) -> dict:
        """Render a bounded non-destructive preview with ffmpeg filters."""
        source = Path(audio_path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(str(source))
        presets = {
            "clean_headroom": "highpass=f=30,alimiter=limit=0.89",
            "guitar_tight": "highpass=f=70,lowpass=f=12000,acompressor=threshold=-18dB:ratio=3:attack=10:release=100",
            "vocal_control": "highpass=f=80,acompressor=threshold=-20dB:ratio=3:attack=8:release=120",
            "master_preview": "acompressor=threshold=-16dB:ratio=2:attack=20:release=150,alimiter=limit=0.89",
        }
        normalized = str(preset or "").strip().lower()
        if normalized not in presets:
            raise ValueError(f"Неизвестный preview preset: {preset}")
        destination = self._preview_root(source) / f"{source.stem}_{normalized}_{uuid.uuid4().hex[:8]}.wav"
        plan = {
            "read_only_source": True,
            "source": str(source),
            "preset": normalized,
            "filter_chain": presets[normalized],
            "output": str(destination),
            "requires_confirmation": True,
            "original_modified": False,
        }
        if not confirmed:
            plan["status"] = "CONFIRMATION_REQUIRED"
            return plan
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(source), "-af", presets[normalized], "-c:a", "pcm_s16le", str(destination)],
                check=True,
                capture_output=True,
                text=True,
                timeout=90,
            )
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"Не удалось создать preview: {exc.stderr[-500:]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Создание preview превысило ограничение времени") from exc
        preview = self.analyze(str(destination))
        return {**plan, "status": "CREATED", "preview_analysis": preview}

    @staticmethod
    def _preview_root(source: Path) -> Path:
        parts = list(source.parts)
        try:
            index = parts.index("data")
        except ValueError:
            return source.parent / "jarvis_previews"
        project_root = Path(*parts[:index])
        return runtime_path(project_root / "backend", "mixing", "renders")

    def suggest_chain(self, audio_path: str, instrument: str = "") -> dict:
        """Suggest a conservative, installed-plugin-aware chain without applying it."""
        analysis = self.analyze(audio_path)
        value = str(instrument or "mix").strip().lower()
        if any(token in value for token in ("vocal", "voice", "вокал", "голос")):
            chain = [
                {"plugin": "iZotope Nectar 3", "purpose": "коррекция и базовая vocal-цепочка"},
                {"plugin": "FabFilter Pro-Q 2", "purpose": "убрать лишний низ и резонансы"},
                {"plugin": "FabFilter Total Bundle", "purpose": "контроль динамики и финальный баланс"},
            ]
        elif any(token in value for token in ("guitar", "гитар", "gtr")):
            chain = [
                {"plugin": "Native Instruments Guitar Rig 5", "purpose": "amp/cabinet и тон"},
                {"plugin": "FabFilter Pro-Q 2", "purpose": "high-pass и контроль резонансов"},
                {"plugin": "FabFilter Total Bundle", "purpose": "контроль динамики и сатурация"},
            ]
        else:
            chain = [
                {"plugin": "FabFilter Pro-Q 2", "purpose": "тональный баланс"},
                {"plugin": "FabFilter Total Bundle", "purpose": "динамика и headroom"},
            ]
        known = {"fabfilter pro-q 2", "fabfilter total bundle", "izotope nectar 3", "native instruments guitar rig 5"}
        for item in chain:
            item["availability"] = "registry_detected" if item["plugin"].lower() in known else "not_verified"
        return {
            "read_only": True,
            "instrument": instrument or "mix",
            "analysis": analysis,
            "suggested_chain": chain,
            "apply": {"available": False, "requires_confirmation": True, "reason": "Применение требует DAW adapter и подтверждения пользователя."},
        }

    def analyze(self, audio_path: str) -> dict:
        path = Path(audio_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(str(path))
        if path.suffix.lower() not in {".wav", ".wave"}:
            raise ValueError("MVP анализирует только WAV без изменения исходного файла")
        with wave.open(str(path), "rb") as source:
            frames = source.readframes(source.getnframes())
            width = source.getsampwidth()
            channels = source.getnchannels()
            rate = source.getframerate()
        if not frames or width not in (1, 2, 3, 4):
            raise ValueError("Пустой или неподдерживаемый WAV")
        peak = 0
        squares = 0.0
        count = 0
        step = width
        for offset in range(0, len(frames) - width + 1, step):
            raw = frames[offset:offset + width]
            value = int.from_bytes(raw, "little", signed=True)
            peak = max(peak, abs(value))
            squares += float(value * value)
            count += 1
        full_scale = float(2 ** (width * 8 - 1))
        peak_dbfs = 20 * math.log10(max(peak / full_scale, 1e-12))
        rms_dbfs = 20 * math.log10(max(math.sqrt(squares / max(count, 1)) / full_scale, 1e-12))
        result = {
            "path": str(path),
            "read_only": True,
            "samplerate": rate,
            "channels": channels,
            "duration": round((len(frames) / max(width * channels * rate, 1)), 3),
            "peak_dbfs": round(peak_dbfs, 2),
            "rms_dbfs": round(rms_dbfs, 2),
            "clipping": peak >= int(full_scale),
        }
        if np is not None and width in (1, 2, 4):
            dtype = {1: np.int8, 2: np.int16, 4: np.int32}[width]
            values = np.frombuffer(frames, dtype=dtype).astype(np.float32) / full_scale
            if channels > 1:
                values = values[: len(values) - (len(values) % channels)].reshape(-1, channels)
                mono = values.mean(axis=1)
            else:
                mono = values
            if len(mono) >= 1024:
                window = np.hanning(len(mono))
                spectrum = np.abs(np.fft.rfft(mono * window))
                frequencies = np.fft.rfftfreq(len(mono), 1.0 / rate)
                bands = {"low_20_120hz": (20, 120), "mid_120_2000hz": (120, 2000), "high_2000_16000hz": (2000, 16000)}
                result["frequency_bands"] = {
                    name: round(float(np.sqrt(np.mean(spectrum[(frequencies >= low) & (frequencies < high)] ** 2))), 6)
                    if np.any((frequencies >= low) & (frequencies < high)) else 0.0
                    for name, (low, high) in bands.items()
                }
            if channels == 2 and len(values) > 1:
                left, right = values[:, 0], values[:, 1]
                result["stereo_correlation"] = round(float(np.corrcoef(left, right)[0, 1]), 4) if np.std(left) and np.std(right) else 0.0
                result["phase_warning"] = result["stereo_correlation"] < 0.0
        result["recommendations"] = self._recommendations(result)
        return result

    def compare(self, mix_path: str, reference_path: str) -> dict:
        mix = self.analyze(mix_path)
        reference = self.analyze(reference_path)
        return {
            "read_only": True,
            "mix": mix,
            "reference": reference,
            "delta": {
                "duration": round(mix["duration"] - reference["duration"], 3),
                "peak_dbfs": round(mix["peak_dbfs"] - reference["peak_dbfs"], 2),
                "rms_dbfs": round(mix["rms_dbfs"] - reference["rms_dbfs"], 2),
            },
            "limitations": [
                "Сравнение не является психоакустическим LUFS-анализом.",
                "Оригинальные файлы не изменяются.",
            ],
        }

    def mastering_report(self, audio_path: str) -> dict:
        report = self.analyze(audio_path)
        loudness = self._loudness_metrics(audio_path)
        report["mastering"] = {
            "true_peak_dbfs": loudness.get("true_peak_dbfs"),
            "integrated_lufs": loudness.get("integrated_lufs"),
            "measurement_method": loudness.get("measurement_method"),
            "rms_proxy_dbfs": report["rms_dbfs"],
            "stereo_width": "not_measured" if report["channels"] < 2 else "correlation_available",
            "status": loudness.get("status", "read_only_measurement"),
        }
        if loudness.get("status") != "measured":
            report["recommendations"].append(loudness.get("error", "LUFS/True Peak не удалось измерить."))
        elif loudness["true_peak_dbfs"] > -1.0:
            report["recommendations"].append("True Peak выше -1 dBFS: оставь запас перед кодированием и публикацией.")
        return report

    def suggest_mastering_chain(self, audio_path: str, genre: str = "", goal: str = "") -> dict:
        """Suggest a genre-aware, non-destructive mastering plan from measured data."""
        report = self.mastering_report(audio_path)
        mastering = report.get("mastering", {})
        lufs = mastering.get("integrated_lufs")
        true_peak = mastering.get("true_peak_dbfs")
        dynamic_range = round(float(report.get("peak_dbfs", 0.0)) - float(report.get("rms_dbfs", 0.0)), 2)
        genre_value = str(genre or "").strip().lower()
        goal_value = str(goal or "").strip()
        if any(token in genre_value for token in ("metal", "rock", "metalcore")):
            target = {"integrated_lufs": "сравнить с плотным metal/rock референсом, не жертвуя атакой", "true_peak_dbfs": "не выше -1.0 dBTP"}
        elif any(token in genre_value for token in ("electronic", "techno", "edm")):
            target = {"integrated_lufs": "сравнить с выбранным электронным референсом", "true_peak_dbfs": "не выше -1.0 dBTP"}
        else:
            target = {"integrated_lufs": "сначала выбрать референс того же жанра", "true_peak_dbfs": "не выше -1.0 dBTP"}
        chain = [
            {"stage": "тональный баланс", "plugin": "iZotope Ozone 9", "parameters": ["EQ", "динамический EQ при необходимости"], "availability": "registry_detected"},
            {"stage": "стереообраз", "plugin": "iZotope Ozone 9", "parameters": ["Imager очень умеренно", "проверка mono compatibility"], "availability": "registry_detected"},
            {"stage": "финальный лимитер", "plugin": "FabFilter Pro-L", "parameters": ["ceiling около -1 dBTP", "gain только по результату сравнения"], "availability": "not_verified_in_registry"},
        ]
        warnings = []
        if report.get("clipping"):
            warnings.append("Сначала устранить клиппинг до лимитирования.")
        if isinstance(true_peak, (int, float)) and true_peak > -1.0:
            warnings.append("True Peak уже выше безопасного запаса; не увеличивать громкость до gain trim.")
        if report.get("phase_warning"):
            warnings.append("Перед расширением проверить фазу и mono compatibility.")
        return {
            "read_only": True,
            "genre": genre,
            "goal": goal_value,
            "measured": {"integrated_lufs": lufs, "true_peak_dbfs": true_peak, "dynamic_range_db": dynamic_range, "stereo_correlation": report.get("stereo_correlation")},
            "target_policy": target,
            "suggested_chain": chain,
            "warnings": warnings,
            "apply": {"available": False, "requires_confirmation": True, "reason": "Применение требует подтверждённого DAW adapter и работы с копией проекта."},
        }

    @classmethod
    def _loudness_metrics(cls, audio_path: str) -> dict:
        """Measure integrated loudness and 4x true peak without changing the WAV.

        This is a small, dependency-light BS.1770-style meter: K-weighting,
        400 ms blocks with 75% overlap, absolute/relative gating, and 4x
        polyphase oversampling for true peak. It intentionally reports the
        method so it is not confused with an offline mastering render.
        """
        if np is None or scipy_signal is None:
            return {"status": "unavailable", "measurement_method": "numpy_scipy_required"}
        try:
            with wave.open(str(Path(audio_path).expanduser().resolve()), "rb") as source:
                frames = source.readframes(source.getnframes())
                width = source.getsampwidth()
                channels = source.getnchannels()
                rate = source.getframerate()
            values = cls._decode_samples(frames, width, channels)
            if values.size == 0 or rate <= 0:
                raise ValueError("пустой аудиопоток")

            # BS.1770 K-weighting approximation. The high-pass removes DC/
            # subsonic energy; the shelf models the ear's high-frequency bias.
            filtered = scipy_signal.sosfilt(
                scipy_signal.butter(2, 38.0, btype="highpass", fs=rate, output="sos"),
                values,
                axis=0,
            )
            shelf = scipy_signal.butter(2, 1681.974, btype="highpass", fs=rate, output="sos")
            high = scipy_signal.sosfilt(shelf, filtered, axis=0)
            weighted = filtered + (10 ** (4.0 / 20.0) - 1.0) * high

            block = max(int(rate * 0.4), 1)
            hop = max(int(block * 0.25), 1)
            if len(weighted) < block:
                blocks = [weighted]
            else:
                blocks = [weighted[start:start + block] for start in range(0, len(weighted) - block + 1, hop)]
            energies = np.asarray([float(np.mean(block_data ** 2)) for block_data in blocks if len(block_data)], dtype=np.float64)
            energies = energies[energies > 1e-12]
            if energies.size == 0:
                integrated = -70.0
            else:
                absolute = energies[10 * np.log10(energies) > -70.0]
                if absolute.size == 0:
                    integrated = -70.0
                else:
                    absolute_lufs = -0.691 + 10 * np.log10(np.mean(absolute))
                    relative_gate = absolute_lufs - 10.0
                    gated = absolute[10 * np.log10(absolute) > relative_gate + 0.691]
                    integrated = float(-0.691 + 10 * np.log10(np.mean(gated if gated.size else absolute)))

            oversampled = scipy_signal.resample_poly(values, 4, 1, axis=0)
            true_peak = float(np.max(np.abs(oversampled)))
            true_peak_dbfs = 20 * math.log10(max(true_peak, 1e-12))
            return {
                "status": "measured",
                "integrated_lufs": round(float(integrated), 2),
                "true_peak_dbfs": round(true_peak_dbfs, 2),
                "measurement_method": "BS.1770-style K-weighted gated blocks + 4x polyphase true peak",
            }
        except Exception as exc:  # meter failure must not break read-only analysis
            return {
                "status": "error",
                "measurement_method": "numpy_scipy_bs1770_style",
                "error": f"LUFS/True Peak measurement failed: {exc}",
            }

    @staticmethod
    def _decode_samples(frames: bytes, width: int, channels: int):
        if width == 1:
            raw = np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0
            scale = 128.0
        elif width == 2:
            raw = np.frombuffer(frames, dtype="<i2").astype(np.float32)
            scale = 32768.0
        elif width == 4:
            raw = np.frombuffer(frames, dtype="<i4").astype(np.float32)
            scale = 2147483648.0
        elif width == 3:
            packed = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3)
            raw = (packed[:, 0].astype(np.int32) | (packed[:, 1].astype(np.int32) << 8) | (packed[:, 2].astype(np.int32) << 16))
            raw = np.where(raw & 0x800000, raw - 0x1000000, raw).astype(np.float32)
            scale = 8388608.0
        else:
            raise ValueError(f"неподдерживаемая разрядность WAV: {width} байт")
        if channels < 1 or raw.size % channels:
            raise ValueError("повреждённая межканальная раскладка WAV")
        return (raw.reshape(-1, channels) / scale).astype(np.float32)

    @staticmethod
    def _recommendations(result: dict) -> list[str]:
        recommendations = []
        if result.get("clipping"):
            recommendations.append("Проверь gain staging: обнаружен цифровой клиппинг.")
        if result.get("peak_dbfs", 0) > -1.0:
            recommendations.append("Оставь больше запаса до 0 dBFS перед мастерингом.")
        if result.get("phase_warning"):
            recommendations.append("Проверь стерео в моно и взаимную фазу каналов.")
        if not recommendations:
            recommendations.append("Критических проблем по базовым метрам не обнаружено; проверь материал в контексте микса.")
        return recommendations
