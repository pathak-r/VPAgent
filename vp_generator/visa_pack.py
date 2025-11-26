"""Core orchestration logic for generating visa packs."""

from __future__ import annotations

import json
import logging
from typing import Dict, List

from .models import (
    TripRequest,
    TripPlan,
    DayPlan,
    FlightOption,
    HotelOption,
    VisaRules,
    VisaPackDocuments,
)
from .utils import make_date_list, truncate_summary, format_friendly_date, format_friendly_datetime
from .llm import llm_call, get_client
from .services.flights import recommend_flights
from .services.hotels import recommend_hotels
from .services.insurance import recommend_insurance


logger = logging.getLogger(__name__)


def apply_budget_band_to_plan(trip_plan: TripPlan) -> None:
    band = (trip_plan.request.budget_band or "medium").lower()
    if band == "low":
        min_inr, max_inr = 100_000, 150_000
    elif band == "medium":
        min_inr, max_inr = 150_000, 300_000
    elif band == "high":
        min_inr, max_inr = 300_000, None
    else:
        min_inr, max_inr = 150_000, 300_000
    trip_plan.budget_per_person_min_inr = min_inr
    trip_plan.budget_per_person_max_inr = max_inr


def apply_rules_agent(trip_request: TripRequest) -> VisaRules:
    schengen_countries = {
        "austria",
        "belgium",
        "bulgaria",
        "croatia",
        "czechia",
        "denmark",
        "estonia",
        "finland",
        "france",
        "germany",
        "greece",
        "hungary",
        "iceland",
        "italy",
        "latvia",
        "liechtenstein",
        "lithuania",
        "luxembourg",
        "malta",
        "netherlands",
        "norway",
        "poland",
        "portugal",
        "romania",
        "slovakia",
        "slovenia",
        "spain",
        "sweden",
        "switzerland",
    }
    dest_lower = {c.lower() for c in trip_request.destination_countries}
    if dest_lower & schengen_countries:
        return VisaRules(
            visa_type="Schengen Short-Stay (Type C)",
            min_insurance_coverage_eur=30000,
            typical_required_docs=[
                "Completed & signed visa application form",
                "Passport with required validity and blank pages",
                "Recent passport-sized photographs",
                "Travel medical insurance (min €30,000 coverage)",
                "Round-trip flight reservation",
                "Hotel reservation(s) or proof of accommodation",
                "Proof of sufficient funds (bank statements, salary slips, etc.)",
                "Proof of employment / business / studies",
                "Travel itinerary and cover letter explaining trip purpose",
            ],
            notes="Rules vary by consulate; user must confirm with their specific VFS/consulate.",
        )
    return VisaRules(
        visa_type="Generic Tourist Visa",
        min_insurance_coverage_eur=30000,
        typical_required_docs=[
            "Visa application form",
            "Passport",
            "Photographs",
            "Travel insurance",
            "Travel bookings",
            "Proof of funds",
            "Cover letter",
        ],
        notes="Destination not recognized as Schengen in this prototype.",
    )


def generate_itinerary_segment_structured(trip_plan: TripPlan, segment_dates: List[str]) -> List[DayPlan]:
    req = trip_plan.request
    client = get_client()
    tools = [
        {
            "type": "function",
            "name": "generate_itinerary_segment",
            "description": "Generate one visa-friendly itinerary entry for each given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "date": {"type": "string"},
                                "city": {"type": "string"},
                                "summary": {"type": "string"},
                            },
                            "required": ["date", "city", "summary"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["days"],
                "additionalProperties": False,
            },
            "strict": True,
        }
    ]
    prompt = f"""
    You are a travel planner helping an Indian traveller apply for a Schengen visa.

    Generate an itinerary ONLY for the following dates of the trip:
    {', '.join(segment_dates)}

    For each date, you MUST create exactly ONE day object with:
      - "date": the exact date string from the list above.
      - "city": a city in the destination countries ({', '.join(req.destination_countries)})
               that makes sense for the trip.
      - "summary": a concise 1–2 sentence description of the day's main activities.

    Traveller details:
    - Nationality: {req.nationality}
    - Departure city: {req.departure_city}
    - Destination countries: {', '.join(req.destination_countries)}
    - Overall trip dates: {req.start_date} to {req.end_date}
    - Purpose: {req.purpose}
    - Budget band per person: {req.budget_band}
    - Travellers count: {req.travellers_count}

    Style rules for "summary":
    - 1–2 sentences maximum.
    - Max ~30 words.
    - No bullet points, no lists.
    - No line breaks; just a single paragraph per day.
    - Visa-friendly: typical sightseeing, museums, walking tours, cafes, day trips.
    """
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[{"role": "user", "content": prompt}],
        tools=tools,
        tool_choice={"type": "function", "name": "generate_itinerary_segment"},
        temperature=0.3,
        max_output_tokens=900,
    )
    tool_call = next(
        (
            item
            for item in response.output
            if item.type == "function_call" and item.name == "generate_itinerary_segment"
        ),
        None,
    )
    if tool_call is None:
        raise RuntimeError("Model did not return a generate_itinerary_segment function call.")
    data = json.loads(tool_call.arguments)
    raw_days = data.get("days", [])
    day_plans: List[DayPlan] = []
    for item in raw_days:
        date_str = item.get("date")
        city = item.get("city", req.destination_countries[0])
        summary_raw = item.get("summary", "Sightseeing and local exploration.")
        summary = truncate_summary(summary_raw)
        if date_str not in segment_dates:
            for d in segment_dates:
                if d not in [dp.date for dp in day_plans]:
                    date_str = d
                    break
        if date_str is None:
            date_str = segment_dates[0]
        day_plans.append(DayPlan(date=date_str, city=city, summary=summary))
    existing_by_date = {dp.date: dp for dp in day_plans}
    final_day_plans: List[DayPlan] = []
    for d in segment_dates:
        final_day_plans.append(
            existing_by_date.get(
                d,
                DayPlan(
                    date=d,
                    city=req.destination_countries[0],
                    summary="Sightseeing and local exploration.",
                ),
            )
        )
    return final_day_plans


def plan_itinerary_agent(trip_plan: TripPlan) -> None:
    req = trip_plan.request
    all_dates = make_date_list(req.start_date, req.end_date)
    MAX_DAYS_PER_CALL = 8
    logger.info("Planning itinerary for %s day(s)", len(all_dates))
    all_day_plans: List[DayPlan] = []
    for i in range(0, len(all_dates), MAX_DAYS_PER_CALL):
        segment_dates = all_dates[i : i + MAX_DAYS_PER_CALL]
        try:
            segment_plans = generate_itinerary_segment_structured(trip_plan, segment_dates)
            all_day_plans.extend(segment_plans)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Fallback itinerary used due to error: %s", exc)
            for d in segment_dates:
                all_day_plans.append(
                    DayPlan(date=d, city=req.destination_countries[0], summary="Sightseeing and local exploration.")
                )
    final_plans: List[DayPlan] = []
    used_dates = set()
    for d in all_dates:
        matching = [dp for dp in all_day_plans if dp.date == d and dp.date not in used_dates]
        if matching:
            final_plans.append(matching[0])
            used_dates.add(d)
        else:
            final_plans.append(
                DayPlan(date=d, city=req.destination_countries[0], summary="Sightseeing and local exploration.")
            )
    trip_plan.itinerary = final_plans


def recommend_flights_agent(trip_plan: TripPlan) -> None:
    trip_plan.flights = recommend_flights(trip_plan.request)


def recommend_hotels_agent(trip_plan: TripPlan) -> None:
    if trip_plan.itinerary:
        cities = []
        for day in trip_plan.itinerary:
            if day.city not in cities:
                cities.append(day.city)
    else:
        cities = [trip_plan.request.destination_countries[0]]
    trip_plan.hotels = recommend_hotels(trip_plan.request, cities)


def recommend_insurance_agent(trip_plan: TripPlan) -> None:
    trip_plan.insurance_options = recommend_insurance(trip_plan.request)


def enrich_itinerary(trip_plan: TripPlan) -> None:
    if not trip_plan.itinerary:
        return

    hotels_by_city: Dict[str, List[HotelOption]] = {}
    for hotel in trip_plan.hotels:
        hotels_by_city.setdefault(hotel.city, []).append(hotel)

    theme = (trip_plan.request.trip_theme or "").lower()
    flights = trip_plan.flights

    for idx, day in enumerate(trip_plan.itinerary):
        city_hotels = hotels_by_city.get(day.city, [])
        if not city_hotels and trip_plan.hotels:
            city_hotels = trip_plan.hotels[:3]
        day.stay_options = [format_hotel_option(h) for h in city_hotels[:2]]
        day.activities = themed_activity_suggestions(day.city, theme)

        if idx == 0 and flights:
            inbound = flights[0]
            departure_text = format_friendly_datetime(inbound.depart_datetime)
            arrival_text = format_friendly_datetime(inbound.arrive_datetime)
            arrival_note = (
                f"Arrive via {inbound.airline} flight from {inbound.from_airport}, departing {departure_text} "
                f"and landing {arrival_text}."
            )
            day.activities.insert(0, arrival_note)
            day.transport = f"Arrival flight into {inbound.to_airport}."
        elif idx > 0:
            prev_city = trip_plan.itinerary[idx - 1].city
            day.transport = build_transport_suggestion(prev_city, day.city)
        else:
            day.transport = "Local transit / walking"

        if idx == len(trip_plan.itinerary) - 1 and flights:
            outbound = flights[-1]
            departure_text = format_friendly_datetime(outbound.depart_datetime)
            departure_note = (
                f"Depart via {outbound.airline} flight from {outbound.to_airport} "
                f"to {outbound.from_airport} at {departure_text}."
            )
            day.activities.append(departure_note)
            day.transport = f"Departure flight from {outbound.to_airport}."


def validate_trip_agent(trip_plan: TripPlan) -> None:
    issues = []
    if not trip_plan.itinerary:
        issues.append("No itinerary generated.")
    if not trip_plan.flights:
        issues.append("No flight options generated.")
    if not trip_plan.hotels:
        issues.append("No hotel options generated.")
    trip_plan.validation_issues = issues


def generate_documents_agent(trip_plan: TripPlan) -> None:
    req = trip_plan.request
    rules = trip_plan.rules
    names = req.traveller_names or []
    flights = trip_plan.flights
    primary_country = req.primary_destination_country or req.destination_countries[0]
    flight_line = ""
    if flights:
        outbound = flights[0]
        inbound = flights[-1]
        pronoun = "We" if req.travellers_count > 1 else "I"
        outbound_depart = format_friendly_datetime(outbound.depart_datetime)
        inbound_depart = format_friendly_datetime(inbound.depart_datetime)
        flight_line = (
            f"{pronoun} plan to arrive via {outbound.airline} flight from {outbound.from_airport} "
            f"to {outbound.to_airport} on {outbound_depart} and depart on "
            f"{inbound.airline} flight from {inbound.to_airport} back to {inbound.from_airport} "
            f"on {inbound_depart}."
        )
    if names:
        main_applicant = names[0]
        if len(names) == 1:
            travellers_line = f"Main applicant: {main_applicant} (travelling alone)."
        else:
            others = ", ".join(names[1:])
            travellers_line = f"Main applicant: {main_applicant}. Additional travellers: {others}."
    else:
        main_applicant = "[Applicant's Full Name]"
        travellers_line = "Main applicant name to be inserted manually; travelling alone or with family/friends."
    cover_prompt = f"""
    You are generating a professional cover letter for a Schengen visa application.

    Address it to the Consular Officer of {primary_country}.

    Traveller details:
    - Main applicant: {main_applicant}
    - Additional travellers (if any): {', '.join(names[1:]) if len(names) > 1 else 'None specified'}
    - Travel party size: {req.travellers_count}
    - Nationality: {req.nationality}
    - Country of residence: {req.residence_country}
    - Departure city: {req.departure_city}
    - Destination countries: {', '.join(req.destination_countries)}
    - Trip dates: {req.start_date} to {req.end_date}
    - Purpose: {req.purpose}
    - Budget band per person: {req.budget_band}
    - Flights summary: {flight_line or 'Reservations are attached.'}

    Visa rules context:
    - Visa type: {rules.visa_type if rules else 'Schengen short-stay (tourism)'}
    - Key requirement: Travel insurance, flight and hotel reservations, proof of funds.

    Write a concise, embassy-appropriate cover letter:
    - Addressed to "The Consular Officer, Embassy/Consulate of {primary_country}".
    - Clearly states purpose, dates, main destinations, and travel companions, referencing the flight summary if provided.
    - Mention that the applicant will fund the trip and attach supporting documents.
    - Refer to bookings as reservations/plans. Do not claim they are fully ticketed.
    - Polite, clear, neutral tone.
    - No invented employers/banks/salaries. Use placeholders as needed.
    - End with a polite closing.

    Output: plain text letter, no extra commentary.
    """
    cover_letter = llm_call(cover_prompt)
    table_lines = ["| Date | City | Stay Options | Activities & Notes | Transport |", "| --- | --- | --- | --- | --- |"]
    for day in trip_plan.itinerary:
        stay_text = "<br>".join(day.stay_options) if day.stay_options else "See recommended stays"
        activities_text = "<br>".join(day.activities) if day.activities else day.summary
        transport_text = day.transport or "Local transit / walking"
        row = "| {date} | {city} | {stay} | {acts} | {transport} |".format(
            date=format_friendly_date(day.date),
            city=day.city.replace("|", "/"),
            stay=stay_text.replace("|", "/"),
            acts=activities_text.replace("|", "/"),
            transport=transport_text.replace("|", "/"),
        )
        table_lines.append(row)
    travel_itinerary_text = "\n".join(table_lines)
    flights_lines = [
        f"{f.label}: {f.from_airport} → {f.to_airport}, Depart: {format_friendly_datetime(f.depart_datetime)}, "
        f"Arrive: {format_friendly_datetime(f.arrive_datetime)}, Approx: ₹{int(f.price_in_inr)} (link: {f.booking_link})"
        for f in trip_plan.flights
    ]
    hotels_lines = [
        f"{h.name} ({h.city}) – {format_friendly_date(h.check_in)} to {format_friendly_date(h.check_out)}, "
        f"Approx: ₹{int(h.approx_price_per_night_in_inr)}/night, Address: {h.address}, link: {h.booking_link}"
        for h in trip_plan.hotels
    ]
    checklist_lines = ["Core Required Documents:"]
    if rules:
        for item in rules.typical_required_docs:
            checklist_lines.append(f"- [ ] {item}")
    else:
        checklist_lines.append("- [ ] Check latest requirements with consulate/VFS.")
    trip_plan.documents = VisaPackDocuments(
        cover_letter=cover_letter.strip(),
        travel_itinerary_text=travel_itinerary_text,
        flights_summary="\n".join(flights_lines),
        hotels_summary="\n".join(hotels_lines),
        checklist="\n".join(checklist_lines),
    )


def format_hotel_option(hotel: HotelOption) -> str:
    return (
        f"{hotel.name} (₹{int(hotel.approx_price_per_night_in_inr):,}/night, {hotel.tier.title()}, "
        f"link: {hotel.booking_link})"
    )


def themed_activity_suggestions(city: str, theme: str) -> List[str]:
    base_city = city or "the city"
    if "gastronomic" in theme or "food" in theme:
        return [
            f"Guided food tour sampling bakeries and markets around {base_city}.",
            f"Reserve a chef-led tasting menu or cooking class highlighting regional dishes.",
        ]
    if "grand" in theme or "history" in theme or "culture" in theme:
        return [
            f"Morning museum and landmark circuit through {base_city} with guided commentary.",
            f"Evening heritage walk plus classical performance or gallery visit.",
        ]
    if theme:
        return [
            f"Activities tailored to '{theme}' in {base_city}: curated tours, workshops, or local meetups.",
            f"Free time to pursue personal interests connected to '{theme}'.",
        ]
    return [
        f"Explore iconic sights and neighborhoods around {base_city} at a comfortable pace.",
        "Enjoy local cafes, markets, and a sunset viewpoint or river cruise.",
    ]


def build_transport_suggestion(prev_city: str, next_city: str) -> str:
    if prev_city == next_city:
        return "Local transit / walking day."
    return f"Travel from {prev_city} to {next_city} via train or short intra-Europe flight."


def generate_visa_pack(trip_request: TripRequest) -> TripPlan:
    trip_plan = TripPlan(request=trip_request)
    apply_budget_band_to_plan(trip_plan)
    trip_plan.rules = apply_rules_agent(trip_request)
    plan_itinerary_agent(trip_plan)
    recommend_flights_agent(trip_plan)
    recommend_hotels_agent(trip_plan)
    recommend_insurance_agent(trip_plan)
    enrich_itinerary(trip_plan)
    validate_trip_agent(trip_plan)
    generate_documents_agent(trip_plan)
    return trip_plan
