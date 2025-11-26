# Visa Pack Generator

Prototype for generating visa-ready travel packs. Before running any scripts, set the required environment variables (or create a `.env` file based on `.env.example`).

## Quick Start

1. Copy `.env.example` to `.env` and fill in real secrets.
2. Install dependencies: `pip install -r requirements.txt`.
3. Add provider credentials (Amadeus client id/secret for flights, RapidAPI Booking.com key/host for hotels) to `.env` if you want live data.
4. Run the FastAPI app: `uvicorn vp_generator.api:app --reload`.
5. (Optional) Use `python main.py sample_request.json` to generate a pack from a local JSON payload (a sample request/response lives at the repo root).

The application uses [`python-dotenv`](https://pypi.org/project/python-dotenv/) to load the `.env` file automatically, so once you create `.env` locally you don't need to export the variable manually.

## API Contract

- `GET /health` – simple readiness probe.
- `POST /visa-pack` – accepts the trip request payload and returns the generated plan (mirrors `TripRequest`/`TripPlan`).
  - Flights sourced from the Amadeus Self-Service API; hotels from the Booking.com RapidAPI. Provide valid credentials via `.env` to enable live results.

Export the OpenAPI schema via `uvicorn`/FastAPI tooling to share with the web/mobile clients:

```bash
curl http://localhost:8000/openapi.json -o openapi.json
```

## Sample payloads

- `sample_request.json` – basic two-traveller France trip (includes optional `trip_theme`).
- `sample_response.json` – real response captured via the running API. Helpful for UI prototyping or contract tests.

> Note: the request schema now includes `primary_destination_country`, which should match one of the selected `destination_countries`.

## Testing

Run the backend test suite with:

```bash
pytest
```

## Web & Mobile Clients

- Shared notes live under `clients/` with separate scaffolds for web (`Next.js`) and mobile (`Expo`).
- Regenerate `clients/openapi.json` after backend changes to keep generated types in sync.

Never commit the populated `.env` file or any API keys to version control.
