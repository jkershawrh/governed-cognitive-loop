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
    """Development-only compatibility adapter for the legacy fleet v1 API.

    Ordinary GCL decisions use ProposerAdapter and signed DecisionPackage events.
    This adapter is retained for one explicit local compatibility mode only.
    """

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

        settings = get_settings()
        if (
            settings.runtime_mode == "production"
            or not settings.allow_legacy_fleet_hmac_development_compat
        ):
            return {
                "status": "disabled",
                "reason": (
                    "legacy fleet v1 HMAC compatibility requires "
                    "GCL_ALLOW_LEGACY_FLEET_HMAC_DEVELOPMENT_COMPAT=true "
                    "outside production"
                ),
                "execution_verified": False,
            }

        if not self._url:
            logger.info("Fleet URL not configured, skipping legacy submission: %s", intent.type)
            return {
                "status": "not_sent",
                "legacy_intent": intent.model_dump(),
                "execution_verified": False,
            }

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
                payload = response.json()
                return {
                    "status": "accepted",
                    "remote_response": payload,
                    "transport": "legacy-development-compat",
                    "execution_verified": False,
                }
        except (httpx.HTTPError, Exception) as e:
            logger.warning("Legacy fleet submission failed: %s", e)
            return {
                "status": "deferred",
                "reason": str(e),
                "legacy_intent": intent.model_dump(),
                "execution_verified": False,
            }
