"""Start the local backend and the PySide6 desktop client together."""

from __future__ import annotations

import os
import ctypes
import subprocess
import sys
import time
import traceback
from pathlib import Path

import requests


def _install_crash_log() -> None:
    """Persist frozen-launch exceptions because the GUI build has no console."""
    log_dir = Path(os.getenv("LOCALAPPDATA", Path.home())) / "Jarvis Assist"
    log_path = log_dir / "launcher_crash.log"

    def _hook(exc_type, exc_value, exc_traceback):
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as stream:
                stream.write("\n--- Jarvis launcher crash ---\n")
                traceback.print_exception(exc_type, exc_value, exc_traceback, file=stream)
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = _hook


_install_crash_log()

# PyInstaller keeps PySide6's Qt DLLs in a subdirectory. Register that
# directory before importing QtCore so Windows cannot resolve an incompatible
# Qt6Core.dll from another Python/Qt installation on PATH.
if getattr(sys, "frozen", False):
    _qt_base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    _qt_dll_handles = []
    _qt_loaded_handles = []
    for _qt_dll_dir in (
        _qt_base / "PySide6",
        _qt_base / "_internal" / "PySide6",
        Path(sys.executable).resolve().parent / "_internal" / "PySide6",
    ):
        if _qt_dll_dir.is_dir():
            # Keep handles alive for the whole process; otherwise Windows
            # removes the DLL search directories before QtCore imports.
            _qt_dll_handles.append(os.add_dll_directory(str(_qt_dll_dir)))
            _qt_core = _qt_dll_dir / "Qt6Core.dll"
            if _qt_core.is_file():
                # PySide6's QtCore.pyd may otherwise resolve Qt6Core.dll from
                # another Qt installation before the bundled DLL directory is
                # consulted, producing ERROR_PROC_NOT_FOUND on Windows.
                _qt_loaded_handles.append(ctypes.WinDLL(str(_qt_core)))

try:
    from PySide6.QtCore import QLockFile
except Exception:
    # Keep the original traceback in the local crash log before re-raising so
    # a windowed PyInstaller build remains diagnosable on another PC.
    sys.excepthook(*sys.exc_info())
    raise

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FROZEN_BACKEND = ROOT / "backend_runtime"
HEALTH_URL = "http://127.0.0.1:8000/health"


def wait_for_backend(timeout: float = 25.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if requests.get(HEALTH_URL, timeout=1.0).ok:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.25)
    return False


def main() -> int:
    lock_path = Path(os.getenv("LOCALAPPDATA", Path.home())) / "Jarvis Assist" / "jarvis.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    instance_lock = QLockFile(str(lock_path))
    instance_lock.setStaleLockTime(0)
    if not instance_lock.tryLock(100):
        return 0

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(BACKEND), env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    if getattr(sys, "frozen", False):
        backend_command = [str(FROZEN_BACKEND / "JarvisBackend.exe")]
        backend_cwd = FROZEN_BACKEND
    else:
        backend_command = [sys.executable, str(BACKEND / "main.py")]
        backend_cwd = BACKEND
    backend_process = subprocess.Popen(
        backend_command,
        cwd=str(backend_cwd),
        env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        if not wait_for_backend():
            backend_process.terminate()
            return 2
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from jarvis_ui import main as desktop_main
        return int(desktop_main() or 0)
    finally:
        if backend_process.poll() is None:
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_process.kill()


if __name__ == "__main__":
    raise SystemExit(main())

