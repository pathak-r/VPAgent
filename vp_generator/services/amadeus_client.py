"""Shared helpers for Amadeus API access."""

from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Optional

import httpx

from ..config import get_settings

TOKEN_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"

_cache: dict[str, float | str] = {"token": "", "expires": 0.0}


def get_amadeus_token() -> Optional[str]:
    """Return a cached bearer token or fetch a new one."""

    settings = get_settings()
    if not settings.amadeus_api_key or not settings.amadeus_api_secret:
        return None

    if _cache["token"] and time.time() < _cache["expires"]:
        return _cache["token"]  # type: ignore[return-value]

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.amadeus_api_key,
                    "client_secret": settings.amadeus_api_secret,
                },
            )
            resp.raise_for_status()
            payload = resp.json()
            _cache["token"] = payload.get("access_token", "")
            _cache["expires"] = time.time() + int(payload.get("expires_in", 0)) - 60
            return _cache["token"]  # type: ignore[return-value]
    except Exception:
        return None


def convert_to_inr(amount: float, currency: str) -> float:
    if currency.upper() == "INR":
        return amount
    rates = {"EUR": 90.0, "USD": 83.0}
    return amount * rates.get(currency.upper(), 85.0)


def clamp_dates_for_amadeus(start_date: str, end_date: str) -> tuple[str, str]:
    """Ensure requested dates fall within Amadeus test range (≈330 days)."""

    today = date.today()
    max_start = today + timedelta(days=330)
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        return start_date, end_date

    if start > max_start:
        duration = max((end - start).days, 1)
        start = max_start
        end = start + timedelta(days=duration)

    if end <= start:
        end = start + timedelta(days=1)

    return start.isoformat(), end.isoformat()
