from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config import CONFIG_HOME, RUNTIME_ENV_PATH, WORKSPACE_DIR, STATE_DB_PATH  # noqa: E402


def check_health(url: str = 'http://127.0.0.1:8000/health') -> dict:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            body = response.read().decode('utf-8', errors='replace')
            return {'ok': True, 'body': json.loads(body)}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


def main() -> int:
    report = {
        'python': sys.version,
        'config_home': str(CONFIG_HOME),
        'runtime_env_path': str(RUNTIME_ENV_PATH),
        'runtime_env_exists': RUNTIME_ENV_PATH.exists(),
        'workspace_dir': str(WORKSPACE_DIR),
        'workspace_exists': WORKSPACE_DIR.exists(),
        'state_db_path': str(STATE_DB_PATH),
        'state_db_exists': STATE_DB_PATH.exists(),
        'provider': os.getenv('HEL_LLM_PROVIDER', 'stub'),
        'health': check_health(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
