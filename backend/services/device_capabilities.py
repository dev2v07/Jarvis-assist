"""Optional device and multimodal capability registry.

The registry is intentionally lightweight: importing Jarvis does not load
camera frames, vision models or CAD runtimes.  Each capability reports its
real availability and optional dependencies, so the UI never presents a
placeholder as a working device.
"""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


OPTIONAL_ENV_PYTHON = Path(__file__).resolve().parents[1] / "device_env" / (
    "Scripts\\python.exe" if os.name == "nt" else "bin/python"
)


def _optional_module_available(name: str, *, probe: bool = True) -> bool:
    """Check an optional device module in its isolated dependency environment."""

    if not OPTIONAL_ENV_PYTHON.is_file():
        return False
    if not probe:
        return True
    try:
        result = subprocess.run(
            [
                str(OPTIONAL_ENV_PYTHON),
                "-c",
                "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec(sys.argv[1]) else 1)",
                name,
            ],
            capture_output=True,
            timeout=8,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


class DeviceCapabilityService:
    """Report and lazily exercise Jarvis device adapters."""

    def snapshot(self, *, probe: bool = False) -> dict[str, Any]:
        capabilities = [
            self._camera(),
            self._image_vision(),
            self._gesture(probe=probe),
            self._printer(probe=probe),
            self._cad(probe=probe),
            self._streaming(),
            self._cuda(),
            self._external_devices(probe=probe),
        ]
        if probe:
            for item in capabilities:
                item["checked_at"] = time.time()
        return {
            "schema_version": 1,
            "platform": platform.platform(),
            "capabilities": capabilities,
        }

    def _camera(self) -> dict[str, Any]:
        available = _module_available("cv2")
        return {
            "id": "camera",
            "name": "Камера и видеозахват",
            "available": available,
            "status": "доступно" if available else "модуль OpenCV не установлен",
            "mode": "lazy_capture",
            "details": "Захват открывается только при запросе снимка/потока.",
        }

    def _image_vision(self) -> dict[str, Any]:
        cv = _module_available("cv2")
        pil = _module_available("PIL")
        return {
            "id": "vision",
            "name": "Изображения и распознавание объектов",
            "available": cv or pil,
            "status": "базовая обработка доступна" if (cv or pil) else "зависимости не установлены",
            "mode": "on_demand",
            "details": "Object detection-модель подключается отдельно; приложение не притворяется, что она установлена.",
        }

    def _gesture(self, *, probe: bool = True) -> dict[str, Any]:
        available = _optional_module_available("mediapipe", probe=probe)
        return {
            "id": "gesture",
            "name": "Жестовое управление",
            "available": available,
            "status": "готово к подключению" if available and probe else "среда найдена, модуль не проверен" if available else "MediaPipe не установлен",
            "mode": "on_demand",
            "details": "Камера и MediaPipe не запускаются при обычном голосовом запросе.",
        }

    def _printer(self, *, probe: bool = True) -> dict[str, Any]:
        available = platform.system() == "Windows" and _optional_module_available("win32print", probe=probe)
        return {
            "id": "printer",
            "name": "Принтер",
            "available": available,
            "status": "доступен Windows-адаптер" if available and probe else "среда найдена, модуль не проверен" if available else "адаптер принтера не установлен",
            "mode": "on_demand",
            "details": "Печать будет требовать отдельного подтверждения пользователя.",
        }

    def _cad(self, *, probe: bool = True) -> dict[str, Any]:
        available = _optional_module_available("build123d", probe=probe)
        return {
            "id": "cad",
            "name": "CAD / 3D-генерация",
            "available": available,
            "status": "build123d доступен" if available and probe else "среда найдена, модуль не проверен" if available else "CAD-движок не установлен",
            "mode": "on_demand",
            "details": "Генерация моделей не входит в быстрый путь чата.",
        }

    def _streaming(self) -> dict[str, Any]:
        audio = _module_available("sounddevice")
        video = _module_available("cv2")
        return {
            "id": "streaming",
            "name": "Потоковое аудио/видео",
            "available": audio or video,
            "status": "аудио/видео адаптеры доступны" if (audio or video) else "адаптеры не установлены",
            "mode": "lazy_stream",
            "details": "Голосовой аудиопоток уже обслуживает voice runtime; видеопоток включается отдельно.",
        }

    def _cuda(self) -> dict[str, Any]:
        available = False
        count = 0
        device = "CPU"
        try:
            import torch

            available = bool(torch.cuda.is_available())
            count = int(torch.cuda.device_count()) if available else 0
            if available:
                device = str(torch.cuda.get_device_name(0))
        except Exception as exc:
            return {
                "id": "cuda",
                "name": "CUDA / GPU",
                "available": False,
                "status": "проверка недоступна",
                "mode": "diagnostic",
                "details": type(exc).__name__,
            }
        return {
            "id": "cuda",
            "name": "CUDA / GPU",
            "available": available,
            "status": f"{device}, устройств: {count}" if available else "CUDA не активна, используется CPU",
            "mode": "diagnostic",
            "details": "Проверка не запускает обучение и не меняет драйверы.",
        }

    def _external_devices(self, *, probe: bool = True) -> dict[str, Any]:
        available = _optional_module_available("zeroconf", probe=probe)
        return {
            "id": "external_devices",
            "name": "Внешние устройства / LAN discovery",
            "available": available,
            "status": "обнаружение доступно" if available and probe else "среда найдена, модуль не проверен" if available else "zeroconf не установлен",
            "mode": "on_demand",
            "details": "Сканирование сети не выполняется при открытии приложения.",
        }

    async def capture_camera(self, index: int = 0, output_dir: str | Path = "") -> dict[str, Any]:
        """Capture one frame without loading a persistent camera worker."""

        import asyncio

        return await asyncio.to_thread(self._capture_camera_sync, int(index), Path(output_dir))

    @staticmethod
    def _capture_camera_sync(index: int, output_dir: Path) -> dict[str, Any]:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("OpenCV не установлен") from exc
        output_dir.mkdir(parents=True, exist_ok=True)
        camera = cv2.VideoCapture(index)
        try:
            ok, frame = camera.read()
            if not ok or frame is None:
                raise RuntimeError(f"Камера {index} не вернула кадр")
            path = output_dir / f"camera_{int(time.time() * 1000)}.jpg"
            if not cv2.imwrite(str(path), frame):
                raise RuntimeError("Не удалось сохранить кадр")
            return {"path": str(path), "index": index, "size": [int(frame.shape[1]), int(frame.shape[0])]}
        finally:
            camera.release()


device_capabilities = DeviceCapabilityService()
