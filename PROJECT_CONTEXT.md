# VisaDocsFast / VPAgent – Project Context

Use this file as the quick briefing for new sessions. It summarizes what the repo contains, how the product works today, and which APIs/keys are involved so future chats can ramp up immediately.

## Goal

Build **VisaDocsFast**, a service that assembles a Schengen visa travel pack for travelers. The pack must include:

- Primary destination logic following Schengen rules (longest stay / first entry).
- Indicative flights, hotels, and insurance suggestions.
- A professional cover letter and a day‑by‑day itinerary.
- A checklist for consulate submission.

We are moving from a rules-based FastAPI workflow to a LangChain/LangGraph "VPAgent" so the system can search the web (Tavily) and generate richer content via Anthropic/OpenAI.

## Repo layout

- `vp_generator/api.py` – FastAPI app. Exposes two endpoints:
  - `POST /visa-pack` (legacy rules/Amadeus/Hotelbeds implementation).
  - `POST /visa-pack/agent` (LangGraph/Tavily agent).
- `vp_generator/langgraph_agent.py` – LangGraph workflow imported from LangChain Builder. Nodes:
  1. Flights via Exa agentic search (falls back to Tavily).
  2. Hotels via Exa agentic search (falls back to Tavily).
  3. Insurance via Exa agentic search (falls back to Tavily).
  4. Cover letter + itinerary generation via Claude/OpenAI.
  5. Preview + final output summarizer.
- `clients/web/visa-pack-web` – Next.js playground form to exercise either endpoint (currently wired to `/visa-pack/agent`).
- `main.py` + `sample_request.json` – CLI sample that still calls the legacy engine.

## Environment / secrets

`.env.example` includes both legacy and agent keys. Important ones:

- **Legacy providers**: `OPENAI_API_KEY`, `AMADEUS_*`, `TRAVEL_PAYOUTS_*`, `RAPIDAPI_*`, `AVIASALES_PARTNER_ID`, `HOTELBEDS_*`, `SERPAPI_KEY`.
- **LangGraph agent**: `OPENAI_MODEL`, `ANTHROPIC_API_KEY` (default model `claude-3-5-sonnet-latest`), `TAVILY_API_KEY`, `EXA_API_KEY`, `LANGSMITH_API_KEY` (optional tracing), `LANGCHAIN_TRACING_V2`, `LANGCHAIN_PROJECT`.

FastAPI loads `.env` at boot via `vp_generator/config.py`. When running `uvicorn`, ensure the working directory is the repo root so the file is discovered.

## Current state

- Both endpoints are available; the web UI now posts to `/visa-pack/agent` and renders Tavily-derived flights/hotels/insurance plus the LLM-generated cover letter/itinerary.
- Tavily search is still instantiated via `langchain_community.tools.TavilySearchResults`; plan is to migrate to `langchain_tavily.TavilySearch` to silence deprecation warnings.
- Anthropic model names rotate frequently; we default to `claude-3-5-sonnet-latest`. If Anthropic is unavailable, the code falls back to OpenAI (`OPENAI_MODEL`).
- CORS allows `http://localhost:3000`/`127.0.0.1:3000` for the Next.js UI.

## Testing steps

1. Install deps: `pip install -r requirements.txt` (+ `npm install` under `clients/web/visa-pack-web`).
2. `cp .env.example .env` and fill in keys.
3. Start FastAPI: `uvicorn vp_generator.api:app --reload` from repo root.
4. Start Next.js client: `cd clients/web/visa-pack-web && npm run dev`.
5. Submit the form; network request hits `/visa-pack/agent` and returns JSON containing flights/hotels/insurance, cover letter, itinerary markdown, etc.

## TODO / known gaps

- Replace deprecated `TavilySearchResults` with `langchain_tavily` package.
- Better parse Tavily results (currently heuristics for dates/prices/ratings).
- Add explicit user-input bridging in LangGraph for future human-in-the-loop experiences.
- Eventually retire the old `/visa-pack` implementation once the new agent is fully validated.

Keep this context file updated when major architecture or API decisions change.
