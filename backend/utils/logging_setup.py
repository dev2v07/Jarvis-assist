from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            'ts': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        for attr in ('event', 'request_id', 'agent', 'step', 'status', 'path', 'url', 'provider', 'attempt'):
            value = getattr(record, attr, None)
            if value not in (None, ''):
                payload[attr] = value
        if record.exc_info:
            payload['exc_info'] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_configured = False


def configure_logging(log_dir: Path, level: str = 'INFO') -> None:
    global _configured
    if _configured:
        return

    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = JsonFormatter(datefmt='%Y-%m-%dT%H:%M:%S')

    file_handler = RotatingFileHandler(
        log_dir / 'jarvis_backend.log',
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8',
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(stream_handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
