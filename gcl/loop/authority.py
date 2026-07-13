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


async def check_authority(action_type: str, action_id: str) -> dict:
    """Check with the agent-promotion-line whether this action is within authority.

    Returns: {"verdict": "allow"|"refuse"|"route_human", "reason": "...", "ceiling": float}
    Only the explicit standalone-test runtime may bypass an unavailable service.
    """
    settings = get_settings()
    if not settings.authority_url:
        if settings.runtime_mode == "standalone-test":
            return {
                "verdict": "allow",
                "reason": "explicit standalone-test authority bypass",
                "ceiling": 1.0,
                "consequence_score": CONSEQUENCE_SCORES.get(action_type, 0.5),
            }
        return {
            "verdict": "refuse",
            "reason": "authority service is not configured",
            "ceiling": 0.0,
            "consequence_score": CONSEQUENCE_SCORES.get(action_type, 0.5),
        }

    consequence = CONSEQUENCE_SCORES.get(action_type, 0.5)

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{settings.authority_url}/api/v1/authority/gate",
                json={
                    "agent_id": settings.authority_agent_id,
                    "action_id": action_id,
                    "consequence_score": consequence,
                },
            )
            if resp.status_code == 200:
                return resp.json()
            logger.warning("Authority service returned %d", resp.status_code)
    except (httpx.HTTPError, Exception) as e:
        logger.debug("Authority service unavailable: %s", e)

    if settings.runtime_mode == "standalone-test":
        return {
            "verdict": "allow",
            "reason": "explicit standalone-test authority bypass after service failure",
            "ceiling": 1.0,
            "consequence_score": consequence,
        }
    return {
        "verdict": "refuse",
        "reason": "authority service unavailable, fail-closed",
        "ceiling": 0.0,
        "consequence_score": consequence,
    }
