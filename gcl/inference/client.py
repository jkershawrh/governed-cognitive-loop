from __future__ import annotations

import json
import logging
import os
from typing import Optional

import httpx
from pydantic import BaseModel

from gcl.config import get_settings

logger = logging.getLogger(__name__)

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


async def _validate_with_guardian(result: InferenceResult) -> Optional[InferenceResult]:
    """Validate LLM response through Guardian sidecar. Returns None if blocked."""
    guardian_url = os.environ.get("GUARDIAN_URL", "")
    if not guardian_url:
        return result

    try:
        parsed = json.loads(result.text)
    except (json.JSONDecodeError, ValueError):
        parsed = {"raw_text": result.text}

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(f"{guardian_url}/validate", json={
                "action": {"type": "llm_response", "response": parsed},
            })
            if resp.status_code == 200:
                verdict = resp.json()
                if not verdict.get("allowed", True):
                    logger.warning(
                        "Guardian blocked LLM response (honesty boundary): %s",
                        verdict.get("reason", "unknown"),
                    )
                    try:
                        from gcl.loop.ledger import LedgerClient
                        ledger = LedgerClient()
                        await ledger.write_entry(
                            "gcl.honesty_boundary_violation",
                            {
                                "reason": verdict.get("reason", ""),
                                "verdict_id": verdict.get("verdict_id", ""),
                                "blocked_content_keys": list(parsed.keys()) if isinstance(parsed, dict) else [],
                            },
                            correlation_id="guardian-" + str(verdict.get("verdict_id", "unknown")),
                        )
                    except Exception:
                        pass
                    return None
    except (httpx.HTTPError, Exception) as e:
        logger.debug("Guardian unavailable, passing through: %s", e)

    return result


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
        result = InferenceResult(
            text=choice["message"]["content"],
            model=data.get("model", settings.llm_model),
            usage=data.get("usage", {}),
        )

    return await _validate_with_guardian(result)
