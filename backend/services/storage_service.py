from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import List

from config import FACTS_PATH, CHROMA_PATH


facts_file = Path(FACTS_PATH) / "facts.json"
documents_file = Path(CHROMA_PATH) / "documents.json"

_lock = threading.Lock()


# -------------------------------------------------------
# INIT STORAGE
# -------------------------------------------------------

def _init_file(path: Path):

    if not path.exists():

        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text("[]", encoding="utf-8")


_init_file(facts_file)
_init_file(documents_file)


# -------------------------------------------------------
# JSON HELPERS
# -------------------------------------------------------

def _read_json(path: Path):

    try:

        return json.loads(path.read_text(encoding="utf-8"))

    except Exception:

        return []


def _write_json(path: Path, payload):

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# -------------------------------------------------------
# FACT STORAGE
# -------------------------------------------------------

def store_fact(fact: str):

    fact = fact.strip()

    if not fact:
        return

    with _lock:

        data = _read_json(facts_file)

        if fact not in data:

            data.append(fact)

            _write_json(facts_file, data)


# -------------------------------------------------------
# FACT RETRIEVAL
# -------------------------------------------------------

def retrieve_facts(query: str) -> List[str]:

    query = query.lower()

    facts = _read_json(facts_file)

    results = []

    for fact in facts:

        if query in fact.lower():

            results.append(fact)

        if len(results) >= 5:

            break

    return results


# -------------------------------------------------------
# DOCUMENT STORAGE
# -------------------------------------------------------

def add_document(text: str, metadata: dict | None = None):

    text = text.strip()

    if not text:
        return

    with _lock:

        data = _read_json(documents_file)

        data.append(
            {
                "text": text,
                "metadata": metadata or {},
            }
        )

        _write_json(documents_file, data)


# -------------------------------------------------------
# CONTEXT RETRIEVAL
# -------------------------------------------------------

def retrieve_context(query: str, limit: int = 3) -> str:

    query = query.lower()

    docs = _read_json(documents_file)

    matches = []

    for doc in docs:

        text = doc.get("text", "")

        if query in text.lower():

            matches.append(text)

        if len(matches) >= limit:

            break

    return "\n\n".join(matches)