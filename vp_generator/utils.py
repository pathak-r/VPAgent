"""Utility helpers."""

from datetime import datetime, timedelta
import re
from typing import List, Optional

FRIENDLY_DATE_FMT = "%A %b %d %Y"


def make_date_list(start_date_str: str, end_date_str: str) -> List[str]:
    start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    dates: List[str] = []
    current = start
    while current <= end:
        dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def truncate_summary(summary: str, max_words: int = 30, max_sentences: int = 2) -> str:
    text = summary.replace("\n", " ").strip()
    sentence_parts = re.split(r'(?<=[.!?])\s+', text)
    sentence_parts = [s for s in sentence_parts if s]
    if len(sentence_parts) > max_sentences:
        sentence_parts = sentence_parts[:max_sentences]
    truncated = " ".join(sentence_parts)
    words = truncated.split()
    if len(words) > max_words:
        truncated = " ".join(words[:max_words]) + "…"
    return truncated


def _parse_iso(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value)
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def format_friendly_date(value: str) -> str:
    """Return a user-friendly date heading like 'Monday Nov 24 2025'."""

    parsed = _parse_iso(value)
    if not parsed:
        return value
    return parsed.strftime(FRIENDLY_DATE_FMT)


def format_friendly_datetime(value: str) -> str:
    """Return 'Monday Nov 24 2025 at 2:30 PM' style formatting."""

    parsed = _parse_iso(value)
    if not parsed:
        return value
    time_str = parsed.strftime("%I:%M %p").lstrip("0")
    return f"{parsed.strftime(FRIENDLY_DATE_FMT)} at {time_str}"
