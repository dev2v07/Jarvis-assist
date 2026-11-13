"""Register bundled Qt DLL directories before the frozen entry point imports PySide6."""

import os
import sys
from pathlib import Path

_base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
_handles = []
for _directory in (
    _base,
    _base / "PySide6",
    _base / "_internal",
    _base / "_internal" / "PySide6",
    Path(sys.executable).resolve().parent,
    Path(sys.executable).resolve().parent / "PySide6",
):
    if _directory.is_dir():
        _handles.append(os.add_dll_directory(str(_directory)))
