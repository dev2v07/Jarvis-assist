from pathlib import Path


# =========================================================
# BASE PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

WORKSPACE_DIR = BASE_DIR / "workspace"
LOG_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads"

FACTS_PATH = DATA_DIR / "facts"
CHROMA_PATH = DATA_DIR / "chroma"

# =========================================================
# BACKUP SETTINGS
# =========================================================

BACKUP_ROOT = BASE_DIR / "backups"

# как часто делать backup (часы)
BACKUP_SCHEDULE_HOURS = 6

# =========================================================
# LLM SETTINGS
# =========================================================

# Keep the default aligned with the model currently installed on this PC.
# Override with HEL_OLLAMA_MODEL to select another local model.
OLLAMA_MODEL = "qwen3:8b"

# =========================================================
# LLM RETRY / CACHE
# =========================================================

RETRY_BACKOFF_SECONDS = 2
SEARCH_CACHE_TTL = 300

# =========================================================
# NETWORK SETTINGS
# =========================================================

NETWORK_MAX_RETRIES = 3
NETWORK_REQUEST_TIMEOUT = 10

# =========================================================
# SECURITY / POLICY SETTINGS
# =========================================================

# разрешённые домены для сетевых запросов
SAFE_NETWORK_DOMAINS = [
    "google.com",
    "youtube.com",
    "github.com",
    "stackoverflow.com",
    "wikipedia.org",
]

# запрещённые системные пути Windows
WINDOWS_SYSTEM_PATHS = [
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
]

# =========================================================
# DIRECTORY INITIALIZATION
# =========================================================

REQUIRED_DIRS = [
    WORKSPACE_DIR,
    LOG_DIR,
    DATA_DIR,
    UPLOAD_DIR,
    FACTS_PATH,
    CHROMA_PATH,
    BACKUP_ROOT,
]

for directory in REQUIRED_DIRS:
    directory.mkdir(parents=True, exist_ok=True)

# =========================================================
# VOICE ASSISTANT SETTINGS
# =========================================================

from dotenv import load_dotenv
import os

load_dotenv(BASE_DIR / "dev.env")

# ---------------------------------------------
# Основные параметры ассистента
# ---------------------------------------------

VA_NAME = "Jarvis"
VA_VER = "2.0"

# ---------------------------------------------
# Wake words
# ---------------------------------------------

WAKE_WORDS = [
    "jarvis",
    "джарвис",
    "жарвис",
    "дарвис",
    "зарвис",
    "дарвец",
    "джар из",
    "зарбис",
    "нарвес",
    "диарвис",
    "завис",
    "зарес",
    "червис",
    "жаркость",
    "джар!",
    "джервис",
    "джервис!",
    "джармис!",
    "дервис!",
    "дервис",
    "здравия желаю",
    "джарлис, привет!",
    "джарлис",
    "джаррис",
    "джарбис",
    "джарбиус!",
    "джарбис",
    "джарбис!",
    "джармис"
]

# ---------------------------------------------
# Слова-паразиты команды
# ---------------------------------------------

VA_TBR = (
    "скажи",
    "покажи",
    "ответь",
    "произнеси",
    "расскажи",
    "сколько",
    "слушай"
)

# ---------------------------------------------
# микрофон
# ---------------------------------------------

MICROPHONE_INDEX = None

# ---------------------------------------------
# Chrome
# ---------------------------------------------

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe %s"

# ---------------------------------------------
# OpenAI
# ---------------------------------------------

OPENAI_TOKEN = os.getenv("OPENAI_TOKEN")

if not OPENAI_TOKEN:
    print("WARNING: OPENAI_TOKEN не найден в dev.env")

# =========================================================
# UNIFIED RUNTIME CONFIGURATION
# =========================================================
# Этот блок является совместимым контрактом для services/config_service.py,
# state_store.py и будущих desktop/web/mobile клиентов.

API_PORT = int(os.getenv("JARVIS_API_PORT", "8000"))

OLLAMA_BASE_URL = os.getenv(
    "HEL_OLLAMA_BASE_URL",
    "http://127.0.0.1:11434",
)

OPENAI_API_KEY = os.getenv("HEL_OPENAI_API_KEY", "") or OPENAI_TOKEN or ""
OPENAI_BASE_URL = os.getenv(
    "HEL_OPENAI_BASE_URL",
    "https://api.openai.com/v1",
)
OPENAI_MODEL = os.getenv("HEL_OPENAI_MODEL", "gpt-4o-mini")

LLM_PROVIDER = os.getenv("HEL_LLM_PROVIDER", "ollama").lower()
LLM_REQUEST_TIMEOUT = int(os.getenv("HEL_LLM_REQUEST_TIMEOUT", "45"))
LLM_MAX_RETRIES = int(os.getenv("HEL_LLM_MAX_RETRIES", "2"))

CONFIG_HOME = BASE_DIR / "config"
CONFIG_HOME.mkdir(parents=True, exist_ok=True)

STATE_DB_PATH = DATA_DIR / "jarvis_state.sqlite3"
REQUEST_HISTORY_LIMIT = int(os.getenv("JARVIS_REQUEST_HISTORY_LIMIT", "100"))


def _runtime_env_path() -> Path:
    return CONFIG_HOME / ".env"


def read_runtime_config(mask_secrets: bool = True) -> dict[str, str]:
    """Read user runtime settings without exposing secrets in logs/UI."""

    path = _runtime_env_path()
    values: dict[str, str] = {}

    if path.exists():
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")

    if mask_secrets:
        for key in list(values):
            if "KEY" in key or "TOKEN" in key or "SECRET" in key:
                values[key] = "***" if values[key] else ""

    return values


def update_runtime_config(updates: dict[str, str]) -> None:
    """Persist runtime settings and update this process immediately."""

    path = _runtime_env_path()
    current = read_runtime_config(mask_secrets=False)
    current.update({str(k): str(v) for k, v in updates.items()})

    lines = [
        "# Jarvis runtime configuration",
        *[f"{key}={value}" for key, value in sorted(current.items())],
        "",
    ]

    temp_path = path.with_suffix(".tmp")
    temp_path.write_text("\n".join(lines), encoding="utf-8")
    temp_path.replace(path)

    for key, value in updates.items():
        os.environ[str(key)] = str(value)
