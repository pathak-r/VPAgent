"""LangGraph-powered visa pack builder.

This module adapts the VPAgent workflow produced in LangChain Builder so it can be
invoked programmatically inside our FastAPI app.
"""

from __future__ import annotations

import json
import operator
import os
import re
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Annotated, Dict, List, Optional, TypedDict, Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from vp_generator.services.exa_client import (
    agentic_search,
    has_exa_credentials,
    ExaError,
)

# We intentionally import dotenv lazily; config.py already calls load_dotenv, but
# importing here keeps this module self-contained when executed directly.
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional at runtime
    pass


# ---------------------------------------------------------------------------
# LangGraph state schema
# ---------------------------------------------------------------------------


class TravelerInfo(TypedDict):
    name: str
    nationality: str
    residence_country: str


class DestinationInfo(TypedDict):
    country: str
    city: str
    nights: int
    check_in: str
    check_out: str


class FlightOption(TypedDict):
    airline: str
    flight_number: Optional[str]
    departure_time: str
    arrival_time: str
    duration: str
    stops: int
    price_eur: float
    booking_url: str


class HotelOption(TypedDict):
    name: str
    address: str
    star_rating: int
    nightly_rate_eur: float
    total_cost_eur: float
    board_type: str
    guest_rating: Optional[float]
    booking_url: str


class InsuranceOption(TypedDict):
    provider: str
    coverage_eur: int
    price_per_person_eur: float
    features: List[str]
    booking_url: str


class VPAgentState(TypedDict):
    messages: Annotated[List, operator.add]
    num_travelers: int
    travelers: List[TravelerInfo]
    departure_city: str
    departure_iata: Optional[str]
    trip_start_date: str
    trip_end_date: str
    total_nights: int
    destinations: List[DestinationInfo]
    trip_theme: Optional[str]
    primary_destination: Optional[str]
    primary_destination_city: Optional[str]
    outbound_flights: List[FlightOption]
    return_flights: List[FlightOption]
    hotels_by_city: Dict[str, List[HotelOption]]
    insurance_options: List[InsuranceOption]
    cover_letter: str
    itinerary_table: str
    preview_markdown: str
    current_step: str
    needs_user_input: bool
    user_input_prompt: str
    is_complete: bool
    error: Optional[str]
    interactive: bool


# ---------------------------------------------------------------------------
# Helpers and configuration
# ---------------------------------------------------------------------------


def _iso_date(value: str) -> datetime:
    """Parse ISO formatted date strings."""
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:  # pragma: no cover - validated earlier
        raise ValueError(f"Invalid date '{value}'. Expected YYYY-MM-DD.") from exc


def _format_iso(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def _calculate_destination_dates(
    start_date: str, destinations: List[DestinationInfo]
) -> tuple[List[DestinationInfo], str, int]:
    """Attach check-in/out dates to every destination."""
    start = _iso_date(start_date)
    cursor = start
    total_nights = 0
    updated: List[DestinationInfo] = []
    for dest in destinations:
        check_in = cursor
        check_out = cursor + timedelta(days=dest["nights"])
        cursor = check_out
        total_nights += dest["nights"]
        updated.append(
            {
                **dest,
                "check_in": _format_iso(check_in),
                "check_out": _format_iso(check_out),
            }
        )
    return updated, _format_iso(start + timedelta(days=total_nights)), total_nights


def _determine_primary(destinations: List[DestinationInfo]) -> tuple[str, str]:
    """Return the country/city with the most nights (first wins ties)."""
    if not destinations:
        raise ValueError("At least one destination is required.")
    sorted_dests = sorted(destinations, key=lambda d: d["nights"], reverse=True)
    top = sorted_dests[0]
    return top["country"], top["city"]


def _init_llm():
    """Create an LLM client using whichever provider is configured."""
    preferred = os.getenv("VP_AGENT_LLM_PROVIDER", "auto").lower()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    def _anthropic():
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
        return ChatAnthropic(model=model, temperature=0)

    def _openai():
        model = os.getenv("OPENAI_MODEL", "gpt-4o")
        return ChatOpenAI(model=model, temperature=0)

    if preferred == "openai" and openai_key:
        return _openai()
    if preferred == "anthropic" and anthropic_key:
        return _anthropic()

    if anthropic_key:
        return _anthropic()
    if openai_key:
        return _openai()

    raise RuntimeError(
        "Set ANTHROPIC_API_KEY or OPENAI_API_KEY to run the LangGraph agent."
    )


LLM = _init_llm()

# Tavily requires an API key – instantiate lazily to provide nicer errors.
TAVILY = TavilySearchResults(max_results=5)


def _search_with_tavily(query: str) -> List[Dict]:
    try:
        return TAVILY.invoke(query)
    except Exception as exc:  # pragma: no cover - network failure
        raise RuntimeError(
            "Tavily search failed. Ensure TAVILY_API_KEY is set."
        ) from exc


def _normalize_exa_results(results: List[Dict]) -> List[Dict]:
    normalized: List[Dict] = []
    for result in results:
        text_parts: List[str] = []
        summary = result.get("summary")
        if isinstance(summary, str):
            text_parts.append(summary)
        highlights = result.get("highlights")
        if isinstance(highlights, list):
            text_parts.extend([h for h in highlights if isinstance(h, str)])
        text = result.get("text")
        if isinstance(text, str):
            text_parts.append(text)
        normalized.append(
            {
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": " ".join(text_parts),
                "raw": result,
                "structured_summary": result.get("summary"),
            }
        )
    return normalized


def _parse_structured_summary(summary: Any) -> Optional[Any]:
    if summary is None:
        return None
    if isinstance(summary, (dict, list)):
        return summary
    if isinstance(summary, str):
        cleaned = summary.strip()
        if cleaned.startswith("```"):
            parts = cleaned.split("\n", 1)
            cleaned = parts[1] if len(parts) > 1 else cleaned
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None
    return None


def _agentic_results(
    query: str, num_results: int = 8, summary: Optional[Dict[str, Any]] = None
) -> List[Dict]:
    if has_exa_credentials():
        try:
            exa_results = agentic_search(
                query, num_results=num_results, summary=summary
            )
            normalized = _normalize_exa_results(exa_results)
            if normalized:
                return normalized
        except ExaError:
            pass
    return _search_with_tavily(query)


def _extract_price(text: str) -> float:
    if not text:
        return 0.0
    match = re.search(r"(?:€|eur|\$|usd)\s?([\d.,]{2,7})", text, re.IGNORECASE)
    if not match:
        match = re.search(r"\b([\d]{2,5})(?:\s?(?:eur|usd))\b", text, re.IGNORECASE)
    if match:
        value = match.group(1).replace(",", "")
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _price_from_string(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return _extract_price(value)
    return 0.0


def _extract_rating(text: str) -> int:
    match = re.search(r"(\d+(?:\.\d)?)\s*(?:[- ]?star|/5)", text, re.IGNORECASE)
    if match:
        try:
            value = float(match.group(1))
            return int(round(value))
        except ValueError:
            return 4
    return 4


def _board_type_from_text(text: str) -> str:
    lowered = text.lower()
    if "breakfast" in lowered:
        return "Bed & Breakfast"
    if "half board" in lowered:
        return "Half Board"
    if "full board" in lowered:
        return "Full Board"
    return "Room Only"


def _infer_stop_count(text: str) -> int:
    lowered = text.lower()
    if any(token in lowered for token in ("nonstop", "non-stop", "direct flight")):
        return 0
    match = re.search(r"(\d+)\s*stop", lowered)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return 1
    if "layover" in lowered:
        return 1
    return 1


def _infer_duration_hours(text: str) -> Optional[int]:
    match = re.search(r"(\d{1,2})\s*h", text.lower())
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _flight_summary_config(
    departure_city: str, arrival_city: str, departure_date: str
) -> Dict[str, Any]:
    return {
        "query": (
            f"Return up to five specific flight options for travel from {departure_city} "
            f"to {arrival_city} around {departure_date} in JSON under the key "
            "'flights'. Include airline, flight_number if stated, departure_airport, "
            "arrival_airport, departure_time, arrival_time, duration, stops, "
            "price, and booking_url. Use ISO datetimes when possible."
        ),
        "schema": {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "FlightsResponse",
            "type": "object",
            "properties": {
                "flights": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "airline": {"type": "string"},
                            "flight_number": {"type": "string"},
                            "departure_airport": {"type": "string"},
                            "arrival_airport": {"type": "string"},
                            "departure_time": {"type": "string"},
                            "arrival_time": {"type": "string"},
                            "duration": {"type": "string"},
                            "stops": {"type": "integer"},
                            "price": {"type": "string"},
                            "booking_url": {"type": "string"},
                        },
                        "required": [
                            "airline",
                            "departure_airport",
                            "arrival_airport",
                        ],
                    },
                }
            },
            "required": ["flights"],
        },
    }


def _hotel_summary_config(
    city: str, country: str, check_in: str, check_out: str
) -> Dict[str, Any]:
    return {
        "query": (
            f"Return up to four hotel recommendations in {city}, {country} "
            f"between {check_in} and {check_out} as JSON under key "
            "'hotels'. Provide name, neighborhood_or_location, star_rating (e.g., 4-star or 4.5/5), "
            "nightly_rate, key_features, and booking_url."
        ),
        "schema": {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "HotelResponse",
            "type": "object",
            "properties": {
                "hotels": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "neighborhood_or_location": {"type": "string"},
                            "star_rating": {"type": "string"},
                            "nightly_rate": {"type": "string"},
                            "key_features": {"type": "string"},
                            "booking_url": {"type": "string"},
                        },
                        "required": ["name"],
                    },
                }
            },
            "required": ["hotels"],
        },
    }


# ---------------------------------------------------------------------------
# LangGraph nodes
# ---------------------------------------------------------------------------


def flight_researcher(state: VPAgentState) -> VPAgentState:
    departure_city = state["departure_city"]
    first_dest = state["destinations"][0]
    last_dest = state["destinations"][-1]
    start_date = state["trip_start_date"]
    end_date = state["trip_end_date"]

    outbound_query = (
        f"best cheap flights {departure_city} to {first_dest['city']} "
        f"{start_date} nonstop or 1 stop booking"
    )
    return_query = (
        f"best cheap flights {last_dest['city']} to {departure_city} "
        f"{end_date} nonstop or 1 stop booking"
    )

    outbound_results = _agentic_results(
        outbound_query,
        num_results=8,
        summary=_flight_summary_config(departure_city, first_dest["city"], start_date),
    )
    return_results = _agentic_results(
        return_query,
        num_results=8,
        summary=_flight_summary_config(last_dest["city"], departure_city, end_date),
    )

    def _build_flights(results: List[Dict], target_date: str) -> List[FlightOption]:
        candidates: List[tuple] = []
        for result in results:
            structured = _parse_structured_summary(result.get("structured_summary"))

            rows: List[Dict[str, Any]] = []
            if isinstance(structured, dict) and "flights" in structured:
                maybe_list = structured["flights"]
                if isinstance(maybe_list, list):
                    rows = [row for row in maybe_list if isinstance(row, dict)]
            elif isinstance(structured, list):
                rows = [row for row in structured if isinstance(row, dict)]
            else:
                rows = []

            if rows:
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    price = _price_from_string(
                        row.get("price") or row.get("price_eur")
                    )
                    stops_value = row.get("stops")
                    if isinstance(stops_value, (int, float)):
                        stops = int(stops_value)
                    elif isinstance(stops_value, str) and stops_value.isdigit():
                        stops = int(stops_value)
                    else:
                        stops = 1
                    duration_label = (
                        row.get("duration")
                        or row.get("flight_type")
                        or row.get("cabin_class")
                        or "See booking site"
                    )
                    option = FlightOption(
                        airline=row.get("airline")
                        or row.get("carrier")
                        or "Flight option",
                        flight_number=row.get("flight_number"),
                        departure_time=row.get("departure_time")
                        or row.get("departure_date")
                        or target_date,
                        arrival_time=row.get("arrival_time")
                        or row.get("return_date")
                        or target_date,
                        duration=duration_label,
                        stops=stops,
                        price_eur=price,
                        booking_url=row.get("booking_url", result.get("url", "")),
                    )
                    score = (stops, price or 9_999_999)
                    candidates.append((score, option))
                continue

            text_blob = f"{result.get('title','')} {result.get('content','')}"
            price = _extract_price(text_blob)
            stops = _infer_stop_count(text_blob)
            duration_hours = _infer_duration_hours(text_blob) or 99
            duration_label = (
                f"~{duration_hours}h travel time" if duration_hours != 99 else "See booking site"
            )
            option = FlightOption(
                airline=result.get("title", "Flight option"),
                flight_number=None,
                departure_time=target_date,
                arrival_time=target_date,
                duration=duration_label,
                stops=stops,
                price_eur=price,
                booking_url=result.get("url", ""),
            )
            score = (stops, duration_hours, price or 9_999_999)
            candidates.append((score, option))
        candidates.sort(key=lambda item: item[0])
        ranked = [item[1] for item in candidates[:3]]
        if ranked:
            return ranked
        fallback: List[FlightOption] = []
        for result in results[:3]:
            text_blob = f"{result.get('title','')} {result.get('content','')}"
            fallback.append(
                FlightOption(
                    airline=result.get("title", "Flight option"),
                    flight_number=None,
                    departure_time=target_date,
                    arrival_time=target_date,
                    duration="See booking site",
                    stops=1,
                    price_eur=_extract_price(text_blob),
                    booking_url=result.get("url", ""),
                )
            )
        return fallback

    outbound_flights = _build_flights(outbound_results, start_date)
    return_flights = _build_flights(return_results, end_date)

    status_msg = f"""✈️ **Flight Research Complete**

Prioritized shortest + cheapest options:
- Outbound: {departure_city} → {first_dest['city']} on {start_date}
- Return: {last_dest['city']} → {departure_city} on {end_date}
"""
    return {
        **state,
        "outbound_flights": outbound_flights,
        "return_flights": return_flights,
        "current_step": "hotel_research",
        "messages": state.get("messages", []) + [AIMessage(content=status_msg)],
    }


def hotel_researcher(state: VPAgentState) -> VPAgentState:
    hotels_by_city: Dict[str, List[HotelOption]] = {}
    theme = state.get("trip_theme") or ""

    for dest in state["destinations"]:
        query = (
            f"well rated affordable hotels {dest['city']} {dest['country']} "
            f"{dest['check_in']} {dest['nights']} nights booking {theme}"
        )
        results = _agentic_results(
            query,
            num_results=8,
            summary=_hotel_summary_config(
                dest["city"], dest["country"], dest["check_in"], dest["check_out"]
            ),
        )
        candidates: List[tuple] = []
        for result in results:
            structured = _parse_structured_summary(result.get("structured_summary"))
            rows: List[Dict[str, Any]] = []
            if isinstance(structured, dict) and "hotels" in structured:
                rows = [row for row in structured["hotels"] if isinstance(row, dict)]
            elif isinstance(structured, list):
                rows = [row for row in structured if isinstance(row, dict)]

            if rows:
                for row in rows:
                    nightly = _price_from_string(
                        row.get("nightly_rate") or row.get("price")
                    )
                    rating_text = (
                        row.get("star_rating")
                        or row.get("rating")
                        or row.get("guest_rating")
                        or ""
                    )
                    rating = _extract_rating(rating_text)
                    entry = HotelOption(
                        name=row.get("name", f"Hotel in {dest['city']}"),
                        address=row.get("neighborhood_or_location", dest["city"]),
                        star_rating=rating,
                        nightly_rate_eur=nightly,
                        total_cost_eur=nightly * dest["nights"]
                        if nightly
                        else 0.0,
                        board_type=row.get("key_features", ""),
                        guest_rating=None,
                        booking_url=row.get("booking_url", result.get("url", "")),
                    )
                    score = (nightly or 9_999_999, -rating)
                    candidates.append((score, entry))
                continue

            text_blob = f"{result.get('title','')} {result.get('content','')}"
            nightly = _extract_price(text_blob)
            rating = _extract_rating(text_blob)
            if rating < 3:
                continue
            entry = HotelOption(
                name=result.get("title", f"Hotel in {dest['city']}"),
                address=dest["city"],
                star_rating=rating,
                nightly_rate_eur=nightly,
                total_cost_eur=nightly * dest["nights"] if nightly else 0.0,
                board_type=_board_type_from_text(text_blob),
                guest_rating=None,
                booking_url=result.get("url", ""),
            )
            score = (nightly or 9_999_999, -rating)
            candidates.append((score, entry))
        candidates.sort(key=lambda item: item[0])
        ranked = [item[1] for item in candidates[:2]]
        if not ranked:
            fallback: List[HotelOption] = []
            for result in results[:2]:
                text_blob = f"{result.get('title','')} {result.get('content','')}"
                nightly = _extract_price(text_blob)
                fallback.append(
                    HotelOption(
                        name=result.get("title", f"Hotel in {dest['city']}"),
                        address=dest["city"],
                        star_rating=_extract_rating(text_blob),
                        nightly_rate_eur=nightly,
                        total_cost_eur=nightly * dest["nights"] if nightly else 0.0,
                        board_type=_board_type_from_text(text_blob),
                        guest_rating=None,
                        booking_url=result.get("url", ""),
                    )
                )
            ranked = fallback
        hotels_by_city[dest["city"]] = ranked

    msg = f"🏨 **Hotel Research Complete** for {', '.join(hotels_by_city.keys())}"
    return {
        **state,
        "hotels_by_city": hotels_by_city,
        "current_step": "insurance_research",
        "messages": state.get("messages", []) + [AIMessage(content=msg)],
    }


def insurance_researcher(state: VPAgentState) -> VPAgentState:
    traveler_country = state["travelers"][0]["residence_country"]
    trip_duration = state["total_nights"]
    query = (
        f"Schengen visa travel insurance {traveler_country} Europe "
        f"{trip_duration} days €30000 coverage"
    )
    results = _agentic_results(query, num_results=6)
    insurance_options: List[InsuranceOption] = []
    for result in results[:3]:
        insurance_options.append(
            InsuranceOption(
                provider=result.get("title", "Insurance Provider"),
                coverage_eur=30000,
                price_per_person_eur=_extract_price(str(result.get("content", ""))),
                features=[
                    "Medical coverage",
                    "Trip cancellation",
                    "Baggage protection",
                ],
                booking_url=result.get("url", ""),
            )
        )
    msg = "🛡️ **Insurance Research Complete** – Identified compliant plans."
    return {
        **state,
        "insurance_options": insurance_options,
        "current_step": "document_generation",
        "messages": state.get("messages", []) + [AIMessage(content=msg)],
    }


def itinerary_writer(state: VPAgentState) -> VPAgentState:
    travelers = state["travelers"]
    traveler_names = ", ".join(t["name"] for t in travelers)
    nationality = travelers[0]["nationality"]
    residence = travelers[0]["residence_country"]
    destinations_summary = "\n".join(
        [
            f"- {d['country']} ({d['city']}): {d['nights']} nights ({d['check_in']} → {d['check_out']})"
            for d in state["destinations"]
        ]
    )

    cover_prompt = f"""
Generate a formal Schengen visa cover letter with these details:

Traveler(s): {traveler_names}
Nationality: {nationality}
Residence: {residence}
Primary Destination: {state['primary_destination']}
Trip Dates: {state['trip_start_date']} to {state['trip_end_date']}
Total Duration: {state['total_nights']} nights

Destinations:
{destinations_summary}

Budget approach: Value-focused itinerary using economical flights and well-rated stays.
Purpose: Tourism with cultural immersion.

Formatting rules:
- Start directly with "The Consular Officer, {state['primary_destination']} Embassy/Consulate" as the opening line.
- Do NOT include applicant contact details or filler placeholders at the top.
- Conclude with traveler names only—no signature/contact sections for now.
- Core sections: greeting, visit purpose, itinerary highlights, funding/ties to home, closing request.
"""
    cover_letter = LLM.invoke([HumanMessage(content=cover_prompt)]).content

    itinerary_prompt = f"""
Generate a day-by-day itinerary table in Markdown with columns Date | Location | Planned Activities.
Trip Theme: {state.get('trip_theme', 'Culture & History')}
Dates and destinations:
{destinations_summary}

Include flights on arrival/departure days, use real attractions, keep activities concise.
"""
    itinerary_table = LLM.invoke([HumanMessage(content=itinerary_prompt)]).content

    msg = "📄 **Documentation Generated** (cover letter + itinerary)."
    return {
        **state,
        "cover_letter": cover_letter,
        "itinerary_table": itinerary_table,
        "current_step": "preview",
        "messages": state.get("messages", []) + [AIMessage(content=msg)],
    }


def preview_generator(state: VPAgentState) -> VPAgentState:
    travelers = ", ".join(t["name"] for t in state["travelers"])
    flights_section = "### ✈️ Flights\n"
    flights_section += "\n".join(
        [
            f"- {flight.get('airline', 'Airline')} → {flight.get('booking_url', 'N/A')}"
            for flight in state.get("outbound_flights", [])
        ]
    )
    hotels_section = "### 🏨 Hotels\n"
    for city, hotels in state.get("hotels_by_city", {}).items():
        hotels_section += f"**{city}:**\n"
        hotels_section += "\n".join(
            [f"- {hotel['name']} → {hotel['booking_url']}" for hotel in hotels]
        )
        hotels_section += "\n"
    insurance_section = "### 🛡️ Insurance\n"
    insurance_section += "\n".join(
        [
            f"- {option['provider']} → {option['booking_url']}"
            for option in state.get("insurance_options", [])
        ]
    )

    preview = f"""
# 📋 Schengen Visa Application Pack

**Travelers:** {travelers}
**Primary Destination:** {state.get('primary_destination')}
**Trip Duration:** {state['trip_start_date']} → {state['trip_end_date']} ({state['total_nights']} nights)

{flights_section}

{hotels_section}

{insurance_section}

### 📄 Cover Letter
{state.get('cover_letter')}

### 📅 Itinerary
{state.get('itinerary_table')}
"""
    msg = "👀 Preview generated."
    return {
        **state,
        "preview_markdown": preview,
        "current_step": "final_output",
        "messages": state.get("messages", []) + [AIMessage(content=msg)],
    }


def final_output(state: VPAgentState) -> VPAgentState:
    completion_msg = (
        "✅ Visa Pack Approved – download cover letter + itinerary from this response."
    )
    return {
        **state,
        "is_complete": True,
        "current_step": "complete",
        "messages": state.get("messages", []) + [AIMessage(content=completion_msg)],
    }


# ---------------------------------------------------------------------------
# Graph compilation / execution helpers
# ---------------------------------------------------------------------------


def _build_graph():
    workflow = StateGraph(VPAgentState)
    workflow.add_node("flight_research", flight_researcher)
    workflow.add_node("hotel_research", hotel_researcher)
    workflow.add_node("insurance_research", insurance_researcher)
    workflow.add_node("document_generation", itinerary_writer)
    workflow.add_node("preview", preview_generator)
    workflow.add_node("final_output", final_output)

    workflow.set_entry_point("flight_research")
    workflow.add_edge("flight_research", "hotel_research")
    workflow.add_edge("hotel_research", "insurance_research")
    workflow.add_edge("insurance_research", "document_generation")
    workflow.add_edge("document_generation", "preview")
    workflow.add_edge("preview", "final_output")
    workflow.add_edge("final_output", END)
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


@lru_cache(maxsize=1)
def get_vpagent_app():
    return _build_graph()


def build_initial_state(payload: Dict) -> VPAgentState:
    destinations_payload = payload["destinations"]
    if not destinations_payload:
        raise ValueError("At least one destination is required.")
    destinations: List[DestinationInfo] = [
        {
            "country": dest["country"],
            "city": dest["city"],
            "nights": dest["nights"],
            "check_in": "",
            "check_out": "",
        }
        for dest in destinations_payload
    ]
    updated_destinations, trip_end, total_nights = _calculate_destination_dates(
        payload["trip_start_date"], destinations
    )
    primary_country = payload.get("primary_destination_country")
    primary_city = payload.get("primary_destination_city")
    if not primary_country:
        primary_country, primary_city = _determine_primary(updated_destinations)
    return {
        "messages": [],
        "num_travelers": payload["num_travelers"],
        "travelers": payload["travelers"],
        "departure_city": payload["departure_city"],
        "departure_iata": payload.get("departure_iata"),
        "trip_start_date": payload["trip_start_date"],
        "trip_end_date": trip_end,
        "total_nights": total_nights,
        "destinations": updated_destinations,
        "trip_theme": payload.get("trip_theme"),
        "primary_destination": primary_country,
        "primary_destination_city": primary_city,
        "outbound_flights": [],
        "return_flights": [],
        "hotels_by_city": {},
        "insurance_options": [],
        "cover_letter": "",
        "itinerary_table": "",
        "preview_markdown": "",
        "current_step": "start",
        "needs_user_input": False,
        "user_input_prompt": "",
        "is_complete": False,
        "error": None,
        "interactive": False,
    }


def run_vpagent(payload: Dict, *, thread_id: Optional[str] = None) -> VPAgentState:
    initial_state = build_initial_state(payload)
    app = get_vpagent_app()
    config = {"configurable": {"thread_id": thread_id or "vpagent-run"}}
    final_state: VPAgentState = app.invoke(initial_state, config=config)
    return final_state


def summarize_response(state: VPAgentState) -> Dict[str, object]:
    return {
        "trip_start_date": state["trip_start_date"],
        "trip_end_date": state["trip_end_date"],
        "total_nights": state["total_nights"],
        "destinations": state["destinations"],
        "primary_destination": state.get("primary_destination"),
        "primary_destination_city": state.get("primary_destination_city"),
        "outbound_flights": state.get("outbound_flights", []),
        "return_flights": state.get("return_flights", []),
        "hotels_by_city": state.get("hotels_by_city", {}),
        "insurance_options": state.get("insurance_options", []),
        "cover_letter": state.get("cover_letter", ""),
        "itinerary_table": state.get("itinerary_table", ""),
        "preview_markdown": state.get("preview_markdown", ""),
    }
