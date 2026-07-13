from __future__ import annotations

import logging
from typing import Literal, Optional

import httpx
from pydantic import BaseModel, ConfigDict, Field

from gcl.config import get_settings
from gcl.domain.decision_package import (
    SignedDecisionPackageV1,
    to_cloud_event,
)


logger = logging.getLogger(__name__)
DEFAULT_PROPOSAL_PATH = "/api/v1/proposals/decision-packages"


class ProposalResult(BaseModel):
    """Acknowledgement of proposal transport, never proof of execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["accepted", "deferred", "rejected", "not_configured"]
    package_id: str
    package_digest: str
    proposal_id: Optional[str] = None
    operation_id: Optional[str] = None
    status_url: Optional[str] = None
    reason: Optional[str] = None
    remote_status: Optional[str] = None
    execution_verified: Literal[False] = False


class ProposerAdapter:
    """Publish signed GCL decisions to proposer authority as CloudEvents 1.0."""

    def __init__(
        self,
        url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        *,
        proposal_path: str = DEFAULT_PROPOSAL_PATH,
        timeout_seconds: float = 10.0,
    ):
        settings = get_settings()
        self._url = (url if url is not None else settings.proposer_url).rstrip("/")
        self._token = (
            bearer_token
            if bearer_token is not None
            else settings.proposer_bearer_token
        )
        self._path = "/" + proposal_path.strip("/")
        self._timeout = timeout_seconds
        self._source = settings.decision_event_source
        self._traceparent = settings.traceparent or None
        self._runtime_mode = settings.runtime_mode

    async def propose(self, signed: SignedDecisionPackageV1) -> ProposalResult:
        package = signed.package
        base = {
            "package_id": str(package.package_id),
            "package_digest": signed.digest,
        }
        if not self._url:
            return ProposalResult(
                status="not_configured",
                reason="proposer endpoint is not configured",
                **base,
            )
        if self._runtime_mode == "production" and not self._token:
            return ProposalResult(
                status="rejected",
                reason="production proposer OIDC credential is not configured",
                **base,
            )

        event = to_cloud_event(
            signed,
            source=self._source,
            traceparent=self._traceparent,
        )
        headers = {
            "Content-Type": "application/cloudevents+json",
            "Accept": "application/json",
            "Idempotency-Key": package.idempotency_id,
            "X-Correlation-ID": package.correlation_id,
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._url}{self._path}",
                    content=event.model_dump_json(by_alias=True),
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            logger.warning("Decision proposal delivery deferred: %s", exc)
            return ProposalResult(status="deferred", reason=str(exc), **base)

        payload: dict = {}
        if response.content:
            try:
                decoded = response.json()
                if isinstance(decoded, dict):
                    payload = decoded
            except ValueError:
                payload = {}

        if response.status_code in (200, 201, 202):
            return ProposalResult(
                status="accepted",
                proposal_id=payload.get("proposal_id") or payload.get("intent_id"),
                operation_id=payload.get("operation_id"),
                status_url=payload.get("status_url"),
                remote_status=str(payload.get("status", "accepted")),
                **base,
            )
        if 400 <= response.status_code < 500:
            return ProposalResult(
                status="rejected",
                reason=payload.get("reason")
                or payload.get("detail")
                or f"proposer returned HTTP {response.status_code}",
                **base,
            )
        return ProposalResult(
            status="deferred",
            reason=f"proposer returned HTTP {response.status_code}",
            **base,
        )
