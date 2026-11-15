"""Safe, provider-neutral contract for Ollama research subtasks.

This module validates task/result envelopes only. It never grants the model
filesystem, process or network execution rights.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


TASK_TYPES = {
    "source_analysis", "fact_extraction", "knowledge_draft", "lesson_draft",
    "tutorial", "quiz_generation", "faq_generation", "comparison",
    "classification", "metadata_extraction", "discography_analysis",
    "plugin_manual_analysis", "cubase_manual_analysis", "code_review_draft",
    "troubleshooting_hypotheses",
}
TASK_STATUSES = {"QUEUED", "RUNNING", "COMPLETED", "NEEDS_REVIEW", "FAILED", "TIMEOUT"}


@dataclass
class OllamaTask:
    task_type: str
    module: str
    goal: str
    question: str = ""
    context: str = ""
    source_documents: list[dict[str, Any]] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    expected_output_schema: dict[str, Any] = field(default_factory=dict)
    language: str = "ru"
    model: str = "qwen3:8b"
    priority: int = 3
    timeout: int = 120
    task_id: str = field(default_factory=lambda: f"ollama-{uuid4().hex}")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "QUEUED"

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.task_type not in TASK_TYPES:
            errors.append(f"unsupported task_type: {self.task_type}")
        if not self.module.strip():
            errors.append("module is required")
        if not self.goal.strip():
            errors.append("goal is required")
        if self.status not in TASK_STATUSES:
            errors.append(f"invalid status: {self.status}")
        if self.timeout < 1 or self.timeout > 1800:
            errors.append("timeout must be between 1 and 1800 seconds")
        for index, document in enumerate(self.source_documents):
            if not isinstance(document, dict):
                errors.append(f"source_documents[{index}] must be an object")
            elif not (document.get("url") or document.get("text")):
                errors.append(f"source_documents[{index}] needs url or text")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_result(payload: str | dict[str, Any], task_id: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Parse an Ollama JSON result without treating confidence as verification."""
    errors: list[str] = []
    if isinstance(payload, str):
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as exc:
            return None, [f"invalid_json: {exc.msg}"]
    else:
        value = payload
    if not isinstance(value, dict):
        return None, ["result must be an object"]
    if value.get("task_id") != task_id:
        errors.append("task_id mismatch")
    if value.get("status") not in {"COMPLETED", "NEEDS_REVIEW", "FAILED"}:
        errors.append("result status must be COMPLETED, NEEDS_REVIEW or FAILED")
    for key in ("summary", "content", "claims", "source_mapping", "uncertainties", "contradictions", "missing_information"):
        if key not in value:
            errors.append(f"missing result field: {key}")
    value["needs_human_review"] = bool(value.get("needs_human_review", True))
    # A model confidence score never upgrades a draft to VERIFIED.
    value["verified"] = False
    if errors:
        return None, errors
    return value, []
