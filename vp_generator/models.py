"""Core data models for the visa pack generator."""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


@dataclass
class TripRequest:
    nationality: str
    residence_country: str
    departure_city: str
    destination_countries: List[str]
    primary_destination_country: str
    start_date: str
    end_date: str
    purpose: str
    budget_band: str = "medium"
    travellers_count: int = 1
    traveller_names: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    trip_theme: Optional[str] = None
    country_nights: Dict[str, int] = field(default_factory=dict)
    country_nights: Dict[str, int] = field(default_factory=dict)


@dataclass
class DayPlan:
    date: str
    city: str
    summary: str
    stay_options: List[str] = field(default_factory=list)
    activities: List[str] = field(default_factory=list)
    transport: Optional[str] = None


@dataclass
class FlightOption:
    label: str
    from_airport: str
    to_airport: str
    depart_datetime: str
    arrive_datetime: str
    price_in_inr: float
    airline: str
    booking_link: str


@dataclass
class HotelOption:
    name: str
    city: str
    check_in: str
    check_out: str
    approx_price_per_night_in_inr: float
    tier: str
    address: str
    booking_link: str


@dataclass
class InsuranceOption:
    provider: str
    plan_name: str
    coverage_amount_eur: int
    price_in_inr: float
    highlights: List[str]
    purchase_link: str


@dataclass
class VisaRules:
    visa_type: str
    min_insurance_coverage_eur: int
    typical_required_docs: List[str]
    notes: Optional[str] = None


@dataclass
class VisaPackDocuments:
    cover_letter: str
    travel_itinerary_text: str
    flights_summary: str
    hotels_summary: str
    checklist: str


@dataclass
class TripPlan:
    request: TripRequest
    rules: Optional[VisaRules] = None
    itinerary: List[DayPlan] = field(default_factory=list)
    flights: List[FlightOption] = field(default_factory=list)
    hotels: List[HotelOption] = field(default_factory=list)
    insurance_options: List[InsuranceOption] = field(default_factory=list)
    country_nights: Dict[str, int] = field(default_factory=dict)
    country_nights: dict[str, int] = field(default_factory=dict)
    documents: Optional[VisaPackDocuments] = None
    validation_issues: List[str] = field(default_factory=list)
    budget_per_person_min_inr: Optional[int] = None
    budget_per_person_max_inr: Optional[int] = None


def trip_plan_to_dict(plan: TripPlan) -> Dict[str, Any]:
    """Convenience helper for serializing trip plans in APIs."""

    return asdict(plan)
