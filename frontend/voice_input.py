"""Small, testable helpers for composer voice dictation."""

from __future__ import annotations


def merge_transcript(
    current: str,
    transcript: str,
    position: int | None = None,
    selection_start: int | None = None,
    selection_end: int | None = None,
) -> tuple[str, int]:
    """Insert a recognized fragment without discarding the existing draft."""

    text = str(current or "")
    fragment = " ".join(str(transcript or "").split()).strip()
    if not fragment:
        return text, max(0, min(len(text), int(position or len(text))))

    start = int(position if position is not None else len(text))
    end = start
    if selection_start is not None and selection_end is not None:
        start = max(0, min(len(text), int(selection_start)))
        end = max(start, min(len(text), int(selection_end)))
    else:
        start = max(0, min(len(text), start))

    before = text[:start]
    after = text[end:]
    separator = ""
    if before and not before[-1].isspace():
        separator = " "
    inserted = separator + fragment
    trailing_separator = " " if after and not after[0].isspace() else ""
    inserted += trailing_separator
    result = before + inserted + after
    return result, start + len(inserted)
