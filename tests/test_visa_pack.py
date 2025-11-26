"""Tests for visa pack orchestration helpers."""

from __future__ import annotations

from unittest.mock import patch

from vp_generator.models import TripRequest, TripPlan, DayPlan
from vp_generator.visa_pack import (
    apply_budget_band_to_plan,
    apply_rules_agent,
    generate_visa_pack,
)


def _sample_request(**overrides):
    data = dict(
        nationality="Indian",
        residence_country="India",
        departure_city="Bengaluru (BLR)",
        destination_countries=["France"],
        primary_destination_country="France",
        start_date="2025-06-10",
        end_date="2025-06-12",
        purpose="tourism",
        budget_band="medium",
        travellers_count=2,
        traveller_names=["Rohit", "Anita"],
    )
    data.update(overrides)
    return TripRequest(**data)


def test_apply_budget_band_sets_expected_range():
    req = _sample_request(budget_band="high")
    plan = TripPlan(request=req)
    apply_budget_band_to_plan(plan)
    assert plan.budget_per_person_min_inr == 300_000
    assert plan.budget_per_person_max_inr is None


def test_apply_rules_agent_detects_schengen():
    req = _sample_request(destination_countries=["France", "India"])
    rules = apply_rules_agent(req)
    assert "Schengen" in rules.visa_type


@patch("vp_generator.visa_pack.llm_call", return_value="Mock cover letter")
@patch("vp_generator.visa_pack.generate_itinerary_segment_structured")
def test_generate_visa_pack_with_stubbed_llm(mock_segment, _mock_llm):
    def fake_segment(trip_plan, segment_dates):
        return [DayPlan(date=d, city="Paris", summary="Plan") for d in segment_dates]

    mock_segment.side_effect = fake_segment

    plan = generate_visa_pack(_sample_request())

    assert len(plan.itinerary) == 3
    assert plan.flights
    assert plan.hotels
    assert plan.documents is not None
    assert not plan.validation_issues
