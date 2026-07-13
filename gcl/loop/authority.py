from __future__ import annotations

import logging
from typing import Optional

import httpx

from gcl.config import get_settings

logger = logging.getLogger(__name__)

CONSEQUENCE_SCORES = {
    "no_action": 0.0,
    "pre_warm": 0.2,
    "alert": 0.3,
    "scale": 0.5,
    "shed_load": 0.7,
    "migrate": 0.8,
    "rollback": 0.6,
}


def _bounded_score(value: object, default: float) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return default


async def collect_agent_promotion_attestation(
    action_type: str,
    action_id: str,
) -> Optional[dict]:
    """Collect optional agent-promotion provenance without gating a proposal.

    fleet-llm-d owns admission and authorization. This compatibility call can
    annotate a DecisionPackage, but every result, including refusal or service
    unavailability, remains non-authoritative and cannot suppress submission.
    """
    settings = get_settings()
    if not settings.agent_promotion_url:
        return None

    consequence = CONSEQUENCE_SCORES.get(action_type, 0.5)
    headers = {}
    if settings.agent_promotion_bearer_token:
        headers["Authorization"] = f"Bearer {settings.agent_promotion_bearer_token}"

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(
                f"{settings.agent_promotion_url.rstrip('/')}/api/v1/authority/gate",
                json={
                    "agent_id": settings.proposer_agent_id,
                    "action_id": action_id,
                    "consequence_score": consequence,
                },
                headers=headers,
            )
            if response.status_code == 200:
                payload = response.json()
                if isinstance(payload, dict):
                    verdict = str(payload.get("verdict", "unavailable")).lower()
                    if verdict not in {"allow", "refuse", "route_human"}:
                        verdict = "unavailable"
                    return {
                        "verdict": verdict,
                        "reason": str(payload.get("reason", "")),
                        "consequence_score": _bounded_score(
                            payload.get("consequence_score"), consequence
                        ),
                        "ceiling": _bounded_score(payload.get("ceiling"), 0.0),
                    }
            logger.info(
                "Optional agent-promotion service returned %d",
                response.status_code,
            )
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logger.info("Optional agent-promotion service unavailable: %s", exc)

    return {
        "verdict": "unavailable",
        "reason": "optional agent-promotion attestation unavailable",
        "consequence_score": consequence,
        "ceiling": 0.0,
    }
