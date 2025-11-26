"""OpenAI client helpers."""

from typing import Optional

from openai import OpenAI

from .config import get_settings


_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    """Provide a singleton OpenAI client."""

    global _client
    if _client is None:
        settings = get_settings()
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def llm_call(prompt: str, model: Optional[str] = None, max_output_tokens: Optional[int] = None) -> str:
    """Call the Responses API with sane defaults."""

    settings = get_settings()
    client = get_client()
    response = client.responses.create(
        model=model or settings.openai_model,
        input=prompt,
        max_output_tokens=max_output_tokens or settings.max_output_tokens,
    )
    return response.output[0].content[0].text.strip()
