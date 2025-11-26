"""Simple CLI entry to exercise the visa pack generator."""

import argparse
import json
from pathlib import Path

from vp_generator import TripRequest, generate_visa_pack


def load_sample_request(path: Path) -> TripRequest:
    data = json.loads(path.read_text())
    return TripRequest(**data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a visa pack from a JSON request.")
    parser.add_argument("request_file", type=Path, help="Path to a JSON file describing the trip request")
    parser.add_argument("--output", type=Path, help="Optional path to save the trip plan JSON")
    args = parser.parse_args()

    trip_request = load_sample_request(args.request_file)
    plan = generate_visa_pack(trip_request)
    result = json.dumps(plan.__dict__, default=lambda o: o.__dict__, indent=2)

    if args.output:
        args.output.write_text(result)
        print(f"Trip plan saved to {args.output}")
    else:
        print(result)


if __name__ == "__main__":
    main()
