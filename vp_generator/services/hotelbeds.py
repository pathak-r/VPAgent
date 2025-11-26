"""Hotelbeds connectivity helpers."""

from __future__ import annotations

import hashlib
import time
from typing import Dict, List

import httpx

from ..config import get_settings
from ..models import HotelOption, TripRequest

HOTELBEDS_TEST_ENDPOINT = "https://api.test.hotelbeds.com/hotel-api/1.0/hotels"
DESTINATION_CODES: Dict[str, str] = {
    "paris": "PAR",
    "france": "PAR",
    "amsterdam": "AMS",
    "netherlands": "AMS",
    "berlin": "BER",
    "germany": "BER",
    "madrid": "MAD",
    "spain": "MAD",
    "rome": "ROM",
    "italy": "ROM",
    "vienna": "VIE",
    "austria": "VIE",
    "lisbon": "LIS",
    "portugal": "LIS",
    "athens": "ATH",
    "greece": "ATH",
    "prague": "PRG",
    "czechia": "PRG",
}


def _hotelbeds_signature(api_key: str, api_secret: str) -> str:
    raw = f"{api_key}{api_secret}{int(time.time())}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def search_hotels(request: TripRequest, cities: List[str]) -> List[HotelOption]:
    settings = get_settings()
    api_key = settings.hotelbeds_api_key
    api_secret = settings.hotelbeds_api_secret
    if not api_key or not api_secret:
        return []

    destination_code = "PAR"
    for city in cities:
        if not city:
            continue
        code = DESTINATION_CODES.get(city.lower())
        if code:
            destination_code = code
            break
    stay = {
        "checkIn": request.start_date,
        "checkOut": request.end_date,
    }
    occupancies = [
        {
            "rooms": 1,
            "adults": max(1, request.travellers_count),
            "children": 0,
        }
    ]
    payload = {
        "stay": stay,
        "occupancies": occupancies,
        "destination": {"code": destination_code, "type": "SIMPLE"},
        "filter": {"maxHotels": 4},
    }
    signature = _hotelbeds_signature(api_key, api_secret)
    headers = {
        "Api-Key": api_key,
        "X-Signature": signature,
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(HOTELBEDS_TEST_ENDPOINT, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    hotels = data.get("hotels", {}).get("hotels", [])
    results: List[HotelOption] = []
    for entry in hotels[:4]:
        name = entry.get("name")
        if not name:
            continue
        rate_price = 0.0
        rooms = entry.get("rooms") or []
        board_name = ""
        check_in = request.start_date
        check_out = request.end_date
        if rooms:
            rates = rooms[0].get("rates") or []
            if rates:
                rate = rates[0]
                board_name = rate.get("boardName", "")
                try:
                    rate_price = float(rate.get("net", 0))
                except (TypeError, ValueError):
                    rate_price = 0.0
        address = entry.get("address", {})
        address_line = ""
        if isinstance(address, dict):
            address_line = address.get("content", "")
        link = "https://www.hotelbeds.com"
        hotel_code = entry.get("code") or entry.get("hotelBedsCode")
        if hotel_code:
            link = f"https://www.hotelbeds.com/hotels/{hotel_code}"
        results.append(
            HotelOption(
                name=name,
                city=entry.get("destinationName", cities[0] if cities else "Schengen"),
                check_in=check_in,
                check_out=check_out,
                approx_price_per_night_in_inr=rate_price,
                tier=board_name or "hotelbeds",
                address=address_line,
                booking_link=link,
            )
        )
    return results
