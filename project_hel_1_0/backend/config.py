from __future__ import annotations

from pathlib import Path
import os
import platform


def _load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
SYSTEM_NAME = platform.system().lower()
IS_WINDOWS = SYSTEM_NAME == 'windows'

DEFAULT_CONFIG_HOME = Path(os.getenv('APPDATA', str(PROJECT_DIR / '.hel'))) / 'ProjectHel' if IS_WINDOWS else (Path.home() / '.config' / 'project_hel')
CONFIG_HOME = Path(os.getenv('HEL_CONFIG_HOME', str(DEFAULT_CONFIG_HOME)))
CONFIG_HOME.mkdir(parents=True, exist_ok=True)

_load_dotenv(PROJECT_DIR / '.env')
_load_dotenv(CONFIG_HOME / '.env')

DATA_HOME = Path(os.getenv('HEL_DATA_HOME', str(CONFIG_HOME / 'data')))
LOG_DIR = Path(os.getenv('HEL_LOG_DIR', str(CONFIG_HOME / 'logs')))
WORKSPACE_DIR = Path(os.getenv('HEL_WORKSPACE_DIR', str(Path.home() / 'hel_data')))
UPLOAD_DIR = DATA_HOME / 'uploads'
CHROMA_PATH = DATA_HOME / 'chroma_db'
FACTS_PATH = DATA_HOME / 'facts_db'
BACKUP_ROOT = DATA_HOME / 'backups'
STATE_DB_PATH = DATA_HOME / 'hel_state.sqlite3'

API_HOST = os.getenv('HEL_API_HOST', '127.0.0.1')
API_PORT = int(os.getenv('HEL_API_PORT', '8000'))
CORS_ORIGINS = [
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'http://127.0.0.1:3000',
    'http://localhost:3000',
    'file://',
]

LOG_LEVEL = os.getenv('HEL_LOG_LEVEL', 'INFO')
ENVIRONMENT = os.getenv('HEL_ENV', 'development')

LLM_PROVIDER = os.getenv('HEL_LLM_PROVIDER', 'stub').lower()
LLM_REQUEST_TIMEOUT = int(os.getenv('HEL_LLM_REQUEST_TIMEOUT', '45'))
LLM_MAX_RETRIES = int(os.getenv('HEL_LLM_MAX_RETRIES', '2'))
OLLAMA_BASE_URL = os.getenv('HEL_OLLAMA_BASE_URL', 'http://127.0.0.1:11434')
OLLAMA_MODEL = os.getenv('HEL_OLLAMA_MODEL', 'qwen2.5:7b-q4_K_M')
OPENAI_BASE_URL = os.getenv('HEL_OPENAI_BASE_URL', 'https://api.openai.com/v1')
OPENAI_API_KEY = os.getenv('HEL_OPENAI_API_KEY', '')
OPENAI_MODEL = os.getenv('HEL_OPENAI_MODEL', 'gpt-4o-mini')
OPENAI_TEMPERATURE = float(os.getenv('HEL_OPENAI_TEMPERATURE', '0.2'))

EMBED_MODEL = 'nomic-embed-text'
CACHE_SIZE = 256
SEARCH_CACHE_TTL = 300
BACKUP_SCHEDULE_HOURS = 24
NETWORK_REQUEST_TIMEOUT = int(os.getenv('HEL_NETWORK_REQUEST_TIMEOUT', '20'))
NETWORK_MAX_RETRIES = int(os.getenv('HEL_NETWORK_MAX_RETRIES', '2'))
RETRY_BACKOFF_SECONDS = float(os.getenv('HEL_RETRY_BACKOFF_SECONDS', '1.5'))
REQUEST_HISTORY_LIMIT = int(os.getenv('HEL_REQUEST_HISTORY_LIMIT', '50'))

WINDOWS_SYSTEM_PATHS = [
    r'C:\Windows',
    r'C:\Program Files',
    r'C:\Program Files (x86)',
    r'C:\System Volume Information',
    r'C:\Recovery',
    r'C:\$Recycle.Bin',
    r'C:\boot',
    r'C:\ProgramData',
]

SAFE_NETWORK_DOMAINS = {
    'localhost',
    '127.0.0.1',
    'api.github.com',
    'httpbin.org',
    'jsonplaceholder.typicode.com',
}

for path in [CONFIG_HOME, DATA_HOME, UPLOAD_DIR, CHROMA_PATH, FACTS_PATH, BACKUP_ROOT, WORKSPACE_DIR, LOG_DIR]:
    os.makedirs(path, exist_ok=True)

ENV_TEMPLATE = f'''# Project Hel runtime configuration
HEL_ENV={ENVIRONMENT}
HEL_LOG_LEVEL={LOG_LEVEL}
HEL_API_HOST={API_HOST}
HEL_API_PORT={API_PORT}
HEL_LLM_PROVIDER={LLM_PROVIDER}
HEL_OLLAMA_BASE_URL={OLLAMA_BASE_URL}
HEL_OLLAMA_MODEL={OLLAMA_MODEL}
HEL_OPENAI_BASE_URL={OPENAI_BASE_URL}
HEL_OPENAI_MODEL={OPENAI_MODEL}
HEL_OPENAI_API_KEY=
HEL_LLM_REQUEST_TIMEOUT={LLM_REQUEST_TIMEOUT}
HEL_LLM_MAX_RETRIES={LLM_MAX_RETRIES}
HEL_NETWORK_REQUEST_TIMEOUT={NETWORK_REQUEST_TIMEOUT}
HEL_NETWORK_MAX_RETRIES={NETWORK_MAX_RETRIES}
HEL_RETRY_BACKOFF_SECONDS={RETRY_BACKOFF_SECONDS}
HEL_WORKSPACE_DIR={WORKSPACE_DIR}
HEL_DATA_HOME={DATA_HOME}
HEL_LOG_DIR={LOG_DIR}
'''


def ensure_runtime_config() -> Path:
    env_path = CONFIG_HOME / '.env'
    if not env_path.exists():
        env_path.write_text(ENV_TEMPLATE, encoding='utf-8')
    return env_path


def read_runtime_config(mask_secrets: bool = True) -> dict:
    env_path = ensure_runtime_config()
    data = {}
    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if mask_secrets and 'KEY' in key and value:
            value = value[:4] + '...' + value[-4:] if len(value) > 8 else '***'
        data[key] = value
    return data


def update_runtime_config(updates: dict[str, str]) -> Path:
    env_path = ensure_runtime_config()
    current = read_runtime_config(mask_secrets=False)
    current.update({k: str(v) for k, v in updates.items() if v is not None})
    ordered_keys = [
        'HEL_ENV', 'HEL_LOG_LEVEL', 'HEL_API_HOST', 'HEL_API_PORT',
        'HEL_LLM_PROVIDER', 'HEL_OLLAMA_BASE_URL', 'HEL_OLLAMA_MODEL',
        'HEL_OPENAI_BASE_URL', 'HEL_OPENAI_MODEL', 'HEL_OPENAI_API_KEY',
        'HEL_LLM_REQUEST_TIMEOUT', 'HEL_LLM_MAX_RETRIES',
        'HEL_NETWORK_REQUEST_TIMEOUT', 'HEL_NETWORK_MAX_RETRIES',
        'HEL_RETRY_BACKOFF_SECONDS', 'HEL_WORKSPACE_DIR', 'HEL_DATA_HOME', 'HEL_LOG_DIR'
    ]
    lines = ['# Project Hel runtime configuration']
    for key in ordered_keys:
        value = current.get(key)
        if value is not None:
            lines.append(f'{key}={value}')
    for key in sorted(k for k in current.keys() if k not in ordered_keys):
        lines.append(f'{key}={current[key]}')
    env_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    for key, value in updates.items():
        if value is not None:
            os.environ[key] = str(value)
    return env_path


RUNTIME_ENV_PATH = CONFIG_HOME / '.env'

def masked(value: str | None) -> str:
    value = value or ''
    if not value:
        return ''
    return value[:4] + '...' + value[-4:] if len(value) > 8 else '***'


def read_runtime_env() -> dict:
    return read_runtime_config(mask_secrets=False)


def write_runtime_env(updates: dict[str, str]) -> Path:
    return update_runtime_config(updates)
