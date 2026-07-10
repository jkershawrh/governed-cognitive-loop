from __future__ import annotations

import logging
from typing import Optional

import httpx

from gcl.adapter.intent_mapping import FleetIntent, map_action_to_intent
from gcl.config import get_settings
from gcl.domain.contracts import ActionStep

logger = logging.getLogger(__name__)


class FleetAdapter:
    def __init__(self, url: Optional[str] = None, token: Optional[str] = None):
        settings = get_settings()
        self._url = url or settings.fleet_url
        self._token = token or settings.fleet_token
        self._timeout = 10

    async def actuate(
        self, action_step: ActionStep, correlation_id: str
    ) -> Optional[dict]:
        intent = map_action_to_intent(action_step, correlation_id)
        if intent is None:
            return None

        if not self._url:
            logger.info("Fleet URL not configured, skipping actuation: %s", intent.type)
            return intent.model_dump()

        headers = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._url}/api/v1/intents",
                    json=intent.model_dump(),
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, Exception) as e:
            logger.warning("Fleet actuation failed: %s", e)
            return intent.model_dump()
