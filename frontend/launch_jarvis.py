"""Start the local backend and the PySide6 desktop client together."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import requests
from PySide6.QtCore import QLockFile

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
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
        backend_command = [str(ROOT / "JarvisBackend.exe")]
    else:
        backend_command = [sys.executable, str(BACKEND / "main.py")]
    backend_process = subprocess.Popen(
        backend_command,
        cwd=str(BACKEND),
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

