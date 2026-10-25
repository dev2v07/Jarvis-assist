from __future__ import annotations
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
import psutil
import pandas as pd
import matplotlib.pyplot as plt
from config import WORKSPACE_DIR


def ensure_workspace(path: str | Path) -> Path:
    p = Path(path).resolve()
    ws = Path(WORKSPACE_DIR).resolve()
    if not str(p).startswith(str(ws)):
        return ws
    return p


def list_files_safe(directory: str = '.') -> str:
    path = ensure_workspace(Path(WORKSPACE_DIR) / directory if directory == '.' else directory)
    if not path.exists():
        return 'Каталог не найден.'
    return '\n'.join(sorted(item.name for item in path.iterdir())) or 'Пусто.'


def read_file_safe(path: str) -> str:
    try:
        return Path(path).read_text(encoding='utf-8')
    except Exception as e:
        return f'Ошибка: {e}'


def write_file_safe(path: str, content: str) -> str:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')
        return f'Файл сохранён: {p.resolve()}'
    except Exception as e:
        return f'Ошибка: {e}'


def monitor_performance() -> dict:
    ram = psutil.virtual_memory()
    return {
        'cpu_percent': psutil.cpu_percent(interval=0.5),
        'ram_percent': ram.percent,
        'ram_used_mb': round(ram.used / 1024 / 1024, 1),
        'disk_percent': psutil.disk_usage('/').percent,
    }


def backup_data(source_dirs: list[str], backup_root: str) -> str:
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    backup_dir = Path(backup_root) / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    for src in source_dirs:
        src_path = Path(src)
        if src_path.exists():
            dst = backup_dir / src_path.name
            if src_path.is_dir():
                shutil.copytree(src_path, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src_path, dst)
    archive_path = backup_dir.with_suffix('.zip')
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in backup_dir.rglob('*'):
            if file.is_file():
                zf.write(file, file.relative_to(backup_dir.parent))
    return str(archive_path)


def list_backups(backup_root: str) -> list[str]:
    root = Path(backup_root)
    if not root.exists():
        return []
    return sorted([p.name for p in root.glob('*.zip')], reverse=True)


def create_chart_from_csv(csv_path: str, x_col: str, y_col: str, output_path: str) -> str:
    df = pd.read_csv(csv_path)
    plt.figure()
    plt.plot(df[x_col], df[y_col])
    plt.tight_layout()
    plt.savefig(output_path)
    return output_path
