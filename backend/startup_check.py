import shutil
import requests


def check():

    checks = {}

    checks["python"] = shutil.which("python") is not None
    checks["node"] = shutil.which("node") is not None
    checks["npm"] = shutil.which("npm") is not None
    checks["git"] = shutil.which("git") is not None
    checks["ffmpeg"] = shutil.which("ffmpeg") is not None

    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        checks["ollama"] = r.status_code == 200
    except Exception:
        checks["ollama"] = False

    return checks