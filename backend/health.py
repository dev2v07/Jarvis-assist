import psutil
import requests
import shutil
from pathlib import Path


def system_health():

    status = {}

    # CPU
    status["cpu"] = psutil.cpu_percent(interval=0.5)

    # RAM
    mem = psutil.virtual_memory()
    status["ram_used"] = mem.percent

    # Disk (Windows compatible)
    root = Path.cwd().anchor
    disk = shutil.disk_usage(root)

    status["disk_used"] = round(disk.used / disk.total * 100, 2)

    # Ollama check
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        status["ollama"] = r.status_code == 200
    except Exception:
        status["ollama"] = False

    return status