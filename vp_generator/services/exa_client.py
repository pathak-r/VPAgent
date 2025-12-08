"""Thin Exa API client for agentic search queries."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx


EXA_API_KEY = os.getenv("EXA_API_KEY")
EXA_SEARCH_URL = os.getenv("EXA_SEARCH_URL", "https://api.exa.ai/search")


class ExaError(RuntimeError):
    """Raised when the Exa API returns an error."""


def has_exa_credentials() -> bool:
    return bool(EXA_API_KEY)


def agentic_search(
    query: str,
    *,
    num_results: int = 8,
    summary: Optional[Dict[str, Any]] = None,
    search_type: str = "auto",
) -> List[Dict[str, Any]]:
    """Call Exa's search endpoint with the agentic mode."""

    if not EXA_API_KEY:
        raise ExaError(
            "EXA_API_KEY is not configured. Set it in the environment or .env file."
        )

    payload = {
        "type": search_type,
        "query": query,
        "numResults": num_results,
        "useAutoprompt": True,
    }

    if summary:
        payload["contents"] = {"summary": summary}

    headers = {"x-api-key": EXA_API_KEY}

    try:
        response = httpx.post(
            EXA_SEARCH_URL, json=payload, headers=headers, timeout=30.0
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ExaError(f"Exa search failed: {exc}") from exc

    data = response.json()
    results = data.get("results", [])
    if not isinstance(results, list):
        return []
    return results
