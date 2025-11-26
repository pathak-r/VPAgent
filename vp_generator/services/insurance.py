"""Mock travel insurance recommendation service."""

from __future__ import annotations

from typing import List

from ..models import InsuranceOption, TripRequest


def recommend_insurance(request: TripRequest) -> List[InsuranceOption]:
    base_price = {
        "low": 2_000,
        "medium": 3_500,
        "high": 5_500,
    }.get((request.budget_band or "medium").lower(), 3_500)

    options = [
        InsuranceOption(
            provider="SafeVoyage",
            plan_name="Essential Plan",
            coverage_amount_eur=30_000,
            price_in_inr=base_price,
            highlights=["Covers medical emergencies", "Includes repatriation"],
            purchase_link="https://insurance.example.com/safevoyage",
        ),
        InsuranceOption(
            provider="WanderShield",
            plan_name="Plus Plan",
            coverage_amount_eur=50_000,
            price_in_inr=int(base_price * 1.4),
            highlights=["Lost baggage coverage", "Trip interruption"],
            purchase_link="https://insurance.example.com/wandershield",
        ),
    ]
    return options
