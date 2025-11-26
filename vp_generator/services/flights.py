"""Flight recommendations via Aviasales (Travelpayouts) with Amadeus fallback."""

from __future__ import annotations

import re
from typing import Dict, List

import httpx

from ..models import TripRequest, FlightOption
from ..config import get_settings
from .amadeus_client import clamp_dates_for_amadeus, convert_to_inr, get_amadeus_token


AMADEUS_FLIGHTS_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers"
AVIASALES_URL = "https://api.travelpayouts.com/v1/prices/cheap"

PRIMARY_AIRPORTS: Dict[str, str] = {
    "france": "CDG",
    "germany": "FRA",
    "italy": "FCO",
    "spain": "MAD",
    "netherlands": "AMS",
    "belgium": "BRU",
    "switzerland": "ZRH",
    "austria": "VIE",
    "portugal": "LIS",
    "greece": "ATH",
    "czechia": "PRG",
    "poland": "WAW",
    "hungary": "BUD",
    "sweden": "ARN",
    "finland": "HEL",
    "denmark": "CPH",
    "norway": "OSL",
    "croatia": "ZAG",
    "bulgaria": "SOF",
    "romania": "OTP",
    "slovakia": "BTS",
    "slovenia": "LJU",
    "estonia": "TLL",
    "latvia": "RIX",
    "lithuania": "VNO",
    "luxembourg": "LUX",
    "malta": "MLA",
    "iceland": "KEF",
    "liechtenstein": "ZRH",
}

def recommend_flights(request: TripRequest) -> List[FlightOption]:
    settings = get_settings()
    origin = _extract_iata(request.departure_city)
    destination = PRIMARY_AIRPORTS.get(request.primary_destination_country.lower()) or PRIMARY_AIRPORTS.get(
        request.destination_countries[0].lower(), "CDG"
    )

    avia_options = _fetch_aviasales(settings.travelpayouts_token, settings.aviasales_partner_id, origin, destination)
    if avia_options:
        return avia_options

    token = get_amadeus_token()
    if token:
        amadeus_options = _fetch_amadeus(token, origin, destination, request)
        if amadeus_options:
            return amadeus_options
    return _fallback_recommendations(request)


def _fetch_aviasales(token: str | None, marker: str | None, origin: str, destination: str) -> List[FlightOption]:
    if not token or not marker:
        return []
    params = {
        "origin": origin,
        "destination": destination,
        "token": token,
        "marker": marker,
        "currency": "INR",
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(AVIASALES_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except Exception:
        return []

    data = payload.get("data", {})
    results: List[FlightOption] = []
    for dest_key in data.values():
        for offer in dest_key.values():
            price = float(offer.get("price", 0))
            depart = offer.get("departure_at", "")
            arrive = offer.get("return_at", "")
            airline = offer.get("airline", "Aviasales")
            booking_suffix = depart.split("T")[0].replace("-", "")
            results.append(
                FlightOption(
                    label="Inbound Option",
                    airline=airline,
                    from_airport=origin,
                    to_airport=destination,
                    depart_datetime=depart,
                    arrive_datetime=depart,
                    price_in_inr=price,
                    booking_link=f"https://www.aviasales.com/search/{origin}{destination}{booking_suffix}",
                )
            )
            if arrive:
                return_suffix = arrive.split("T")[0].replace("-", "")
                results.append(
                    FlightOption(
                        label="Outbound Option",
                        airline=airline,
                        from_airport=destination,
                        to_airport=origin,
                        depart_datetime=arrive,
                        arrive_datetime=arrive,
                        price_in_inr=price,
                        booking_link=f"https://www.aviasales.com/search/{destination}{origin}{return_suffix}",
                    )
                )
    return results[:6]


def _fetch_amadeus(token: str, origin: str, destination: str, request: TripRequest) -> List[FlightOption]:
    dep_date, ret_date = clamp_dates_for_amadeus(request.start_date, request.end_date)
    params = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": dep_date,
        "returnDate": ret_date,
        "adults": str(max(1, request.travellers_count)),
        "max": "6",
        "currencyCode": "INR",
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(AMADEUS_FLIGHTS_URL, params=params, headers={"Authorization": f"Bearer {token}"})
            resp.raise_for_status()
            data = resp.json().get("data", [])
            return _parse_flight_offers(data, origin, destination)
    except Exception:
        return []


def _parse_flight_offers(data: List[dict], origin: str, destination: str) -> List[FlightOption]:
    flights: List[FlightOption] = []
    for offer in data[:6]:
        price = float(offer.get("price", {}).get("grandTotal", 0))
        currency = offer.get("price", {}).get("currency", "INR")
        price_in_inr = convert_to_inr(price, currency)
        itineraries = offer.get("itineraries", [])
        if not itineraries:
            continue
        outbound = itineraries[0]
        inbound = itineraries[1] if len(itineraries) > 1 else None
        flights.append(
            FlightOption(
                label="Inbound Option",
                airline=_carrier_name(outbound),
                from_airport=origin,
                to_airport=destination,
                depart_datetime=_segment_time(outbound, 0),
                arrive_datetime=_segment_time(outbound, -1, is_arrival=True),
                price_in_inr=price_in_inr,
                booking_link="https://www.amadeus.com",
            )
        )
        if inbound:
            flights.append(
                FlightOption(
                    label="Outbound Option",
                    airline=_carrier_name(inbound),
                    from_airport=destination,
                    to_airport=origin,
                    depart_datetime=_segment_time(inbound, 0),
                    arrive_datetime=_segment_time(inbound, -1, is_arrival=True),
                    price_in_inr=price_in_inr,
                    booking_link="https://www.amadeus.com",
                )
            )
    return flights


def _segment_time(itinerary: dict, index: int, is_arrival: bool = False) -> str:
    segments = itinerary.get("segments", [])
    if not segments:
        return ""
    segment = segments[index]
    key = "arrival" if is_arrival else "departure"
    info = segment.get(key, {})
    return info.get("at", "")


def _carrier_name(itinerary: dict) -> str:
    segments = itinerary.get("segments", [])
    if not segments:
        return "Amadeus"
    carrier = segments[0].get("carrierCode", "")
    return carrier or "Amadeus"


def _extract_iata(value: str) -> str:
    if not value:
        return "DEL"
    match = re.search(r"\((?P<code>[A-Za-z]{3})\)", value)
    if match:
        return match.group("code").upper()
    return value.strip().split()[0][:3].upper()


def _fallback_recommendations(request: TripRequest) -> List[FlightOption]:
    base_price = {
        "low": 55_000,
        "medium": 70_000,
        "high": 95_000,
    }.get((request.budget_band or "medium").lower(), 70_000)
    dest_airport = PRIMARY_AIRPORTS.get(request.primary_destination_country.lower(), "CDG")
    flights = [
        FlightOption(
            label="Inbound Option",
            airline="Sample Airline",
            from_airport=request.departure_city,
            to_airport=dest_airport,
            depart_datetime=f"{request.start_date}T09:00",
            arrive_datetime=f"{request.start_date}T16:00",
            price_in_inr=base_price,
            booking_link="https://www.amadeus.com",
        ),
        FlightOption(
            label="Outbound Option",
            airline="Sample Airline",
            from_airport=dest_airport,
            to_airport=request.departure_city,
            depart_datetime=f"{request.end_date}T10:00",
            arrive_datetime=f"{request.end_date}T18:00",
            price_in_inr=base_price,
            booking_link="https://www.amadeus.com",
        ),
    ]
    return flights
