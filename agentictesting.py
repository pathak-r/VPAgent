"""Legacy entry point kept for continuity while migrating from Colab."""

from __future__ import annotations

from pprint import pprint

from vp_generator import TripRequest, generate_visa_pack


def main() -> None:
    sample_request = TripRequest(
        nationality="Indian",
        residence_country="India",
        departure_city="Bengaluru (BLR)",
        destination_countries=["France"],
        primary_destination_country="France",
        start_date="2025-06-10",
        end_date="2025-06-18",
        purpose="tourism",
        budget_band="medium",
        travellers_count=2,
        traveller_names=["Rohit Pathak", "Vrushali Malushte"],
    )

    trip_plan = generate_visa_pack(sample_request)
    pprint(trip_plan)


if __name__ == "__main__":
    main()
