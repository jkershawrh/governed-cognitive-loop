from __future__ import annotations

import logging
from typing import Optional

import httpx

from gcl.config import get_settings

logger = logging.getLogger(__name__)

ACTION_SCOPES = {
    "no_action": "fleet.observe",
    "pre_warm": "fleet.pre_warm",
    "scale": "fleet.scale",
    "shed_load": "fleet.shed_load",
    "alert": "fleet.alert",
    "migrate": "fleet.migrate",
    "rollback": "fleet.rollback",
}


async def verify_passport(action_type: str, resource: str = "fleet-llm-d/*") -> dict:
    """Verify the GCL's passport scope covers the proposed action.

    Returns: {"decision": "ALLOW"|"DENY", "reason": "...", ...}
    Returns ALLOW if the passport service is not configured or unreachable.
    """
    settings = get_settings()
    if not settings.passport_url or not settings.passport_id:
        return {"decision": "ALLOW", "reason": "passport service not configured"}

    action_class = ACTION_SCOPES.get(action_type, f"fleet.{action_type}")

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{settings.passport_url}/api/v1/scope/evaluate",
                json={
                    "agent_id": settings.authority_agent_id,
                    "passport_id": settings.passport_id,
                    "requested_action": {
                        "action_class": action_class,
                        "resource": resource,
                    },
                },
            )
            if resp.status_code == 200:
                return resp.json()
            logger.warning("Passport service returned %d", resp.status_code)
    except (httpx.HTTPError, Exception) as e:
        logger.debug("Passport service unavailable: %s", e)

    return {"decision": "ALLOW", "reason": "passport service unavailable, fail-open"}
