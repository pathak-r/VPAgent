"""FastAPI application exposing the visa pack generator."""

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .models import TripRequest, TripPlan
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
