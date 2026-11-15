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


def _write_launch_diagnostic(stage: str) -> None:
    """Write non-secret interpreter facts for isolated runtime diagnostics."""
    raw_path = os.getenv("JARVIS_LAUNCH_DIAGNOSTIC", "").strip()
    if not raw_path:
        return
    try:
        path = Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(
                f"stage={stage} executable={sys.executable} prefix={sys.prefix} "
                f"base_prefix={sys.base_prefix} cwd={Path.cwd()}\n"
            )
    except OSError:
        pass

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
API_BASE_URL = os.getenv(
    "JARVIS_API_BASE_URL",
    f"http://127.0.0.1:{os.getenv('JARVIS_API_PORT', '8000')}",
).rstrip("/")
HEALTH_URL = f"{API_BASE_URL}/health"
VOICE_MODELS_URL = f"{API_BASE_URL}/voice/models"


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


def backend_has_current_voice_registry() -> bool:
    """Reject an orphaned backend from an older Jarvis launch."""
    try:
        payload = requests.get(VOICE_MODELS_URL, timeout=1.0).json()
        model_ids = {str(item.get("model_id")) for item in payload.get("models", [])}
        return {"jarvis", "fish_jarvis", "fish_dean"}.issubset(model_ids)
    except (requests.RequestException, ValueError, AttributeError):
        return False


def default_port_listener() -> str | None:
    """Return the PID occupying the configured local API port, if any."""
    if os.name != "nt":
        return None
    port = os.getenv("JARVIS_API_PORT", "8000")
    try:
        output = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        for line in output.splitlines():
            fields = line.split()
            if len(fields) >= 5 and fields[1].endswith(f":{port}") and fields[3] == "LISTENING":
                return fields[4]
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def main() -> int:
    _write_launch_diagnostic("launcher-start")
    # The launcher owns one interpreter for both backend and desktop UI.  A
    # split runtime (backend venv + unrelated system Python) produces a
    # seemingly healthy API while the Qt client fails later with a missing
    # PySide6 import.  Fail early with an actionable diagnostic instead.
    try:
        import PySide6  # noqa: F401
    except ImportError as exc:
        print(
            "Jarvis UI dependencies are missing in the selected Python "
            f"interpreter ({sys.executable}): {exc}. "
            "Install backend/requirements-optional.txt in this same environment.",
            file=sys.stderr,
        )
        return 3

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
    backend_process = None
    reused_backend = False
    try:
        if wait_for_backend(timeout=1.0):
            if backend_has_current_voice_registry():
                reused_backend = True
            else:
                listener_pid = default_port_listener()
                print(
                    "Jarvis API port is occupied by an incompatible backend; "
                    f"not stopping PID {listener_pid or 'unknown'}. "
                    "Close that process or choose an explicit test port."
                )
                return 4
        if not reused_backend:
            backend_process = subprocess.Popen(
                backend_command,
                cwd=str(backend_cwd),
                env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        if not wait_for_backend():
            if backend_process and backend_process.poll() is None:
                backend_process.terminate()
            return 2
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        _write_launch_diagnostic("before-ui-import")
        from jarvis_ui import main as desktop_main
        return int(desktop_main() or 0)
    finally:
        if backend_process and backend_process.poll() is None:
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_process.kill()


if __name__ == "__main__":
    raise SystemExit(main())

