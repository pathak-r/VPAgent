"""Application configuration helpers."""

from dataclasses import dataclass
import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


@dataclass
class Settings:
    """Holds runtime configuration loaded from the environment."""

    openai_api_key: str
    openai_model: str = "gpt-4.1-mini"
    max_output_tokens: int = 800
    amadeus_api_key: Optional[str] = None
    amadeus_api_secret: Optional[str] = None
    travelpayouts_token: Optional[str] = None
    travelpayouts_marker: Optional[str] = None
    aviasales_partner_id: Optional[str] = None
    rapidapi_key: Optional[str] = None
    rapidapi_host: Optional[str] = None
    serpapi_key: Optional[str] = None
    hotelbeds_api_key: Optional[str] = None
    hotelbeds_api_secret: Optional[str] = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache settings so every module shares the same values."""

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "Please set OPENAI_API_KEY in the environment (e.g., via a .env file)."
        )

    return Settings(
        openai_api_key=api_key,
        amadeus_api_key=os.getenv("AMADEUS_API_KEY"),
        amadeus_api_secret=os.getenv("AMADEUS_API_SECRET"),
        travelpayouts_token=os.getenv("TRAVEL_PAYOUTS_TOKEN"),
        travelpayouts_marker=os.getenv("TRAVEL_PAYOUTS_MARKER"),
        aviasales_partner_id=os.getenv("AVIASALES_PARTNER_ID"),
        rapidapi_key=os.getenv("RAPIDAPI_KEY"),
        rapidapi_host=os.getenv("RAPIDAPI_HOST"),
        serpapi_key=os.getenv("SERPAPI_KEY"),
        hotelbeds_api_key=os.getenv("HOTELBEDS_API_KEY"),
        hotelbeds_api_secret=os.getenv("HOTELBEDS_API_SECRET"),
    )
