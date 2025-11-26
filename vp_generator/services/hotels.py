"""Hotel recommendation providers (SerpApi Google Hotels + Booking.com fallback)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, List, Optional

import httpx

from ..config import get_settings
from ..models import TripRequest, HotelOption
from .hotelbeds import search_hotels as hotelbeds_search

DEFAULT_RAPIDAPI_HOST = "booking-com15.p.rapidapi.com"
SEARCH_DEST_ENDPOINT = "/api/v1/hotels/searchDestination"
SEARCH_HOTELS_ENDPOINT = "/api/v1/hotels/searchHotels"
SERP_API_ENDPOINT = "https://serpapi.com/search"


def recommend_hotels(request: TripRequest, cities: Iterable[str]) -> List[HotelOption]:
    """Return the best available hotel options for itinerary cities."""

    settings = get_settings()
    unique_cities = _dedupe_cities(cities)
    if not unique_cities and request.destination_countries:
        unique_cities = [request.destination_countries[0]]

    hotelbeds_hotels: List[HotelOption] = []
    if settings.hotelbeds_api_key and settings.hotelbeds_api_secret:
        hotelbeds_hotels = hotelbeds_search(request, unique_cities)
    if hotelbeds_hotels:
        return hotelbeds_hotels

    serp_hotels: List[HotelOption] = []
    if settings.serpapi_key:
        serp_hotels = _serpapi_hotels(unique_cities, request, settings.serpapi_key)
    if serp_hotels:
        return serp_hotels

    booking_hotels = _booking_com_hotels(unique_cities, request, settings)
    if booking_hotels:
        return booking_hotels

    return _fallback_hotels(request, unique_cities)


def _lookup_destination(base_url: str, headers: dict, city: str) -> Optional[dict]:
    params = {"query": city, "locale": "en-gb"}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{base_url}{SEARCH_DEST_ENDPOINT}", params=params, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
    except Exception:
        return None

    candidates = []
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            candidates = payload["data"]
        elif isinstance(payload.get("result"), list):
            candidates = payload["result"]
    if not candidates:
        return None
    return candidates[0]


def _booking_com_hotels(cities: List[str], request: TripRequest, settings) -> List[HotelOption]:
    """Fallback provider using Booking.com via RapidAPI."""

    key = settings.rapidapi_key
    if not key:
        return []
    host = settings.rapidapi_host or DEFAULT_RAPIDAPI_HOST
    base_url = f"https://{host}"
    headers = {
        "X-RapidAPI-Key": key,
        "X-RapidAPI-Host": host,
    }

    hotels: List[HotelOption] = []
    for city in cities:
        dest = _lookup_destination(base_url, headers, city)
        if not dest:
            continue
        hotels.extend(_search_booking_hotels(base_url, headers, dest, request))
    return hotels


def _search_booking_hotels(base_url: str, headers: dict, dest_info: dict, request: TripRequest) -> List[HotelOption]:
    dest_id = dest_info.get("dest_id") or dest_info.get("destId")
    search_type = dest_info.get("search_type") or dest_info.get("dest_type") or "CITY"
    if not dest_id:
        return []

    params = {
        "dest_id": dest_id,
        "search_type": search_type,
        "page_number": "1",
        "adults": str(max(1, request.travellers_count)),
        "room_qty": "1",
        "units": "metric",
        "languagecode": "en-us",
        "currency_code": "INR",
        "order_by": "price",
        "checkin_date": request.start_date,
        "checkout_date": request.end_date,
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{base_url}{SEARCH_HOTELS_ENDPOINT}", params=params, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
    except Exception:
        return []

    entries: List[dict] = []
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), dict) and isinstance(payload["data"].get("hotels"), list):
            entries = payload["data"]["hotels"]
        elif isinstance(payload.get("result"), list):
            entries = payload["result"]

    results: List[HotelOption] = []
    for entry in entries[:2]:
        name = entry.get("hotel_name") or entry.get("name")
        if not name:
            continue
        price = _extract_price(entry)
        address = entry.get("address") or entry.get("city_name") or entry.get("district") or dest_info.get("name", "")
        results.append(
            HotelOption(
                name=name,
                city=entry.get("city_name") or dest_info.get("name") or dest_info.get("dest_id", ""),
                check_in=request.start_date,
                check_out=request.end_date,
                approx_price_per_night_in_inr=price,
                tier=_tier_from_class(entry.get("class")),
                address=address,
                booking_link="https://www.booking.com",
            )
        )
    return results


def _serpapi_hotels(cities: List[str], request: TripRequest, api_key: str) -> List[HotelOption]:
    hotels: List[HotelOption] = []
    check_in, check_out = _safe_dates(request.start_date, request.end_date)
    params_base = {
        "engine": "google_hotels",
        "check_in_date": check_in,
        "check_out_date": check_out,
        "adults": str(max(1, request.travellers_count)),
        "currency": "INR",
        "hl": "en",
        "api_key": api_key,
    }
    for city in cities:
        params = dict(params_base, q=f"{city}, {request.primary_destination_country}")
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(SERP_API_ENDPOINT, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            continue

        entries: List[dict] = []
        if isinstance(data, dict):
            if isinstance(data.get("properties"), list):
                entries = data["properties"]
            elif isinstance(data.get("hotels_results"), list):
                entries = data["hotels_results"]

        for entry in entries[:2]:
            option = _parse_serp_entry(entry, city, request, check_in, check_out)
            if option:
                hotels.append(option)
    return hotels


def _parse_serp_entry(entry: dict, city: str, request: TripRequest, check_in: str, check_out: str) -> Optional[HotelOption]:
    name = entry.get("name")
    if not name:
        return None
    price = (
        entry.get("rate_per_night", {}).get("extracted_lowest")
        or entry.get("rate_per_night", {}).get("extracted_before_taxes_fees")
        or entry.get("extracted_price")
        or entry.get("price_breakdown", {}).get("extracted_base_price")
        or 0
    )
    booking_link = entry.get("link") or entry.get("serpapi_property_details_link") or "https://www.google.com/travel/hotels"
    address = entry.get("address") or entry.get("description") or f"{city}, {request.primary_destination_country}"
    tier = entry.get("type") or "hotel"
    return HotelOption(
        name=name,
        city=city,
        check_in=check_in,
        check_out=check_out,
        approx_price_per_night_in_inr=float(price or 0),
        tier=tier.lower(),
        address=address,
        booking_link=booking_link,
    )


def _safe_dates(start_date: str, end_date: str) -> tuple[str, str]:
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        return start_date, end_date
    if end <= start:
        end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _dedupe_cities(cities: Iterable[str]) -> List[str]:
    ordered: List[str] = []
    seen = set()
    for city in cities:
        normalized = (city or "").strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return ordered


def _extract_price(entry: dict) -> float:
    for key in ["priceBreakdown", "composite_price_breakdown"]:
        block = entry.get(key, {})
        gross = block.get("gross_price", {}).get("value")
        if gross:
            return float(gross)
        total = block.get("gross_price")
        if isinstance(total, (int, float)):
            return float(total)
    if entry.get("min_total_price"):
        return float(entry["min_total_price"])
    if entry.get("price"):
        return float(entry["price"])
    return 0.0


def _tier_from_class(value: Optional[float]) -> str:
    try:
        stars = float(value)
    except (TypeError, ValueError):
        return "central"
    if stars >= 4.5:
        return "luxury"
    if stars <= 3:
        return "bnb"
    return "central"


def _fallback_hotels(request: TripRequest, cities: Iterable[str]) -> List[HotelOption]:
    hotels: List[HotelOption] = []
    for city in cities:
        hotels.append(
            HotelOption(
                name=f"{city} Central Hotel",
                city=city,
                check_in=request.start_date,
                check_out=request.end_date,
                approx_price_per_night_in_inr=10_000,
                tier="central",
                address=f"City center, {city}",
                booking_link="https://www.booking.com",
            )
        )
    return hotels
