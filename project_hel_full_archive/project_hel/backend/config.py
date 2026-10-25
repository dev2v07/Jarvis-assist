from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
UPLOAD_DIR = BASE_DIR / 'uploads'
CHROMA_PATH = BASE_DIR / 'chroma_db'
FACTS_PATH = BASE_DIR / 'facts_db'
BACKUP_ROOT = PROJECT_DIR / 'backups'
WORKSPACE_DIR = Path.home() / 'hel_data'

API_HOST = '127.0.0.1'
API_PORT = 8000
CORS_ORIGINS = ['*']

OLLAMA_MODEL = 'qwen2.5:7b-q4_K_M'
EMBED_MODEL = 'nomic-embed-text'
CACHE_SIZE = 256
SEARCH_CACHE_TTL = 300
BACKUP_SCHEDULE_HOURS = 24

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

for path in [UPLOAD_DIR, CHROMA_PATH, FACTS_PATH, BACKUP_ROOT, WORKSPACE_DIR]:
    os.makedirs(path, exist_ok=True)
