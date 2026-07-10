from typing import Optional

import httpx
from pydantic import BaseModel

from gcl.config import get_settings


_force_rules = False


class InferenceResult(BaseModel):
    text: str
    model: str
    usage: dict = {}


def set_force_rules(value: bool) -> None:
    global _force_rules
    _force_rules = value


def get_force_rules() -> bool:
    if _force_rules:
        return True
    return get_settings().force_deterministic


def is_inference_available() -> bool:
    if _force_rules:
        return False
    settings = get_settings()
    return bool(settings.llm_api_base)


async def infer(prompt: str, system: str = "") -> Optional[InferenceResult]:
    if _force_rules:
        return None
    settings = get_settings()
    if not settings.llm_api_base:
        return None

    headers = {}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        response = await client.post(
            f"{settings.llm_api_base}/v1/chat/completions",
            headers=headers,
            json={"model": settings.llm_model, "messages": messages},
        )
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        return InferenceResult(
            text=choice["message"]["content"],
            model=data.get("model", settings.llm_model),
            usage=data.get("usage", {}),
        )
