import subprocess
import time
import psutil


PROCESS_NAME = "main.py"


def is_running(name):

    for p in psutil.process_iter(['cmdline']):

        try:

            cmd = p.info.get("cmdline") or []

            if any(name in part for part in cmd):
                return True

        except Exception:
            pass

    return False


def start_backend():

    print("[WATCHDOG] Перезапуск backend...")

    subprocess.Popen(
        ["python", "main.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


while True:

    if not is_running(PROCESS_NAME):

        start_backend()

    time.sleep(10)