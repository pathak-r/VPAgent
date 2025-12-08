## VisaDocsFast – Prototype

Lightweight workspace for VisaDocsFast. Current stack:

- **Backend**: FastAPI (`vp_generator/`) with agentic helpers that call OpenAI, Amadeus, Hotelbeds, Exa/Tavily, and other APIs to create visa packs.
- **Web Client**: Next.js app under `clients/web/visa-pack-web` for testing the form + preview flow.
- **CLI Sample**: `python main.py sample_request.json` will generate a pack from the sample input.

To try it locally:

1. Copy `.env.example` → `.env` and fill in provider keys (OpenAI, Amadeus, Hotelbeds, Exa, etc.).
2. `pip install -r requirements.txt`
3. Run the API: `uvicorn vp_generator.api:app --reload`
4. (Optional) `cd clients/web/visa-pack-web && npm install && npm run dev`

Use this repo as the public landing pad for prospective API partners; the real product logic will keep evolving in the existing FastAPI + Next.js folders.

## LangGraph VPAgent

The new LangGraph implementation lives in `vp_generator/langgraph_agent.py`. It mirrors the
workflow from LangChain Builder: flight research → hotel research → insurance →
cover letter + itinerary generation. Agentic search uses Exa (with Tavily fallback) so the UI can display structured cards. FastAPI exposes it via:

```
POST /visa-pack/agent
```

Payload:

```json
{
  "travelers": [
    {"name": "Priya Sharma", "nationality": "Indian", "residence_country": "UAE"}
  ],
  "departure_city": "Dubai",
  "trip_start_date": "2025-12-05",
  "destinations": [
    {"country": "France", "city": "Paris", "nights": 5},
    {"country": "Italy", "city": "Rome", "nights": 5}
  ],
  "trip_theme": "culture"
}
```

The graph automatically computes check-in/check-out dates, determines the primary
destination (or uses the one supplied), calls Exa/Tavily for
flights/hotels/insurance, and uses Claude/GPT to write the cover letter + itinerary.
The HTTP response includes all research sections plus the Markdown preview shown in the UI.
