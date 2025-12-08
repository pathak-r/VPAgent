"""FastAPI application exposing the visa pack generator."""

from dataclasses import asdict
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .models import TripRequest, TripPlan
from .langgraph_agent import run_vpagent, summarize_response
from .visa_pack import generate_visa_pack


app = FastAPI(title="Visa Pack Generator", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://localhost:3000",
        "https://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TripRequestPayload(BaseModel):
    nationality: str
    residence_country: str
    departure_city: str
    destination_countries: List[str]
    primary_destination_country: str
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    purpose: str
    budget_band: str = "medium"
    travellers_count: int = 1
    traveller_names: Optional[List[str]] = None
    notes: Optional[str] = None
    trip_theme: Optional[str] = None


ISO_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


class VPTraveler(BaseModel):
    name: str
    nationality: str
    residence_country: str


class VPDestination(BaseModel):
    country: str
    city: str
    nights: int = Field(..., ge=1)


class VPAgentPayload(BaseModel):
    travelers: List[VPTraveler]
    departure_city: str
    departure_iata: Optional[str] = None
    trip_start_date: str = Field(..., pattern=ISO_DATE_PATTERN)
    destinations: List[VPDestination]
    trip_theme: Optional[str] = None
    primary_destination_country: Optional[str] = None
    primary_destination_city: Optional[str] = None


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/visa-pack")
def create_visa_pack(payload: TripRequestPayload) -> Dict[str, Any]:
    try:
        req = TripRequest(**payload.dict())
        plan: TripPlan = generate_visa_pack(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return asdict(plan)


@app.post("/visa-pack/agent")
def create_vpagent_pack(payload: VPAgentPayload) -> Dict[str, Any]:
    data = payload.model_dump()
    if not data["travelers"]:
        raise HTTPException(status_code=400, detail="At least one traveler is required.")
    if not data["destinations"]:
        raise HTTPException(
            status_code=400, detail="At least one destination is required."
        )
    data["num_travelers"] = len(data["travelers"])
    try:
        state = run_vpagent(data, thread_id=f"vpagent-{uuid4()}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return summarize_response(state)
