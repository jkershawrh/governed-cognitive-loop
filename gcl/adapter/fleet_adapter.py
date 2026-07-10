from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import logging
from typing import Optional

import httpx

from gcl.adapter.intent_mapping import FleetIntent, map_action_to_intent
from gcl.config import get_settings
from gcl.domain.contracts import ActionStep

logger = logging.getLogger(__name__)


def _generate_fleet_token(secret: str, subject: str = "governed-cognitive-loop") -> str:
    """Generate an HMAC-SHA256 signed token compatible with fleet-llm-d auth."""
    now = datetime.datetime.now(datetime.timezone.utc)
    claims = {
        "sub": subject,
        "role": "operator",
        "iat": now.isoformat(),
        "exp": (now + datetime.timedelta(hours=24)).isoformat(),
    }
    claims_json = json.dumps(claims, separators=(",", ":")).encode()
    claims_b64 = base64.urlsafe_b64encode(claims_json).rstrip(b"=").decode()
    sig = hmac.new(secret.encode(), claims_json, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    return claims_b64 + "." + sig_b64


class FleetAdapter:
    def __init__(self, url: Optional[str] = None, token: Optional[str] = None):
        settings = get_settings()
        self._url = url or settings.fleet_url
        self._secret = token or settings.fleet_token
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
        if self._secret:
            headers["Authorization"] = f"Bearer {_generate_fleet_token(self._secret)}"

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
