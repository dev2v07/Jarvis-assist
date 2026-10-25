from __future__ import annotations
import json
from pathlib import Path
from typing import List
from config import FACTS_PATH, CHROMA_PATH

facts_file = Path(FACTS_PATH) / 'facts.json'
documents_file = Path(CHROMA_PATH) / 'documents.json'

for file in [facts_file, documents_file]:
    if not file.exists():
        file.write_text('[]', encoding='utf-8')


def _read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def _write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def store_fact(fact: str):
    data = _read_json(facts_file)
    if fact not in data:
        data.append(fact)
        _write_json(facts_file, data)


def retrieve_facts(query: str) -> List[str]:
    query_low = query.lower()
    return [item for item in _read_json(facts_file) if query_low in item.lower()][:5]


def add_document(text: str, metadata: dict | None = None):
    data = _read_json(documents_file)
    data.append({'text': text, 'metadata': metadata or {}})
    _write_json(documents_file, data)


def retrieve_context(query: str, limit: int = 3) -> str:
    query_low = query.lower()
    docs = _read_json(documents_file)
    matches = [item['text'] for item in docs if query_low in item['text'].lower()]
    return '\n\n'.join(matches[:limit])
