from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gcl.adapter.proposer_adapter import ProposerAdapter
from gcl.committer.committer import Committer
from gcl.config import get_settings
from gcl.domain.contracts import ActionStep, FalsificationResult
from gcl.domain.enums import Verdict
from gcl.loop.ledger import LedgerClient
from tests.test_decision_package import _signed_package


class TestProposerAdapter:
    @pytest.mark.asyncio
    async def test_missing_endpoint_is_not_execution(self):
        result = await ProposerAdapter(url="").propose(_signed_package())
        assert result.status == "not_configured"
        assert result.execution_verified is False

    @pytest.mark.asyncio
    async def test_production_without_oidc_credential_fails_closed(self, monkeypatch):
        monkeypatch.setenv("GCL_RUNTIME_MODE", "production")
        get_settings.cache_clear()
        result = await ProposerAdapter(
            url="https://proposer.example.test",
            bearer_token="",
        ).propose(_signed_package())
        assert result.status == "rejected"
        assert "OIDC" in result.reason
        assert result.execution_verified is False

    @pytest.mark.asyncio
    async def test_posts_structured_cloudevent_and_normalizes_acknowledgement(self):
        response = MagicMock()
        response.status_code = 202
        response.content = b'{"status":"executed","operation_id":"op-1"}'
        response.json.return_value = {
            "status": "executed",
            "operation_id": "op-1",
        }
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.post = AsyncMock(return_value=response)

        signed = _signed_package()
        with patch("gcl.adapter.proposer_adapter.httpx.AsyncClient", return_value=client):
            result = await ProposerAdapter(
                url="https://proposer.example.test",
                bearer_token="oidc-token",
            ).propose(signed)

        assert result.status == "accepted"
        assert result.remote_status == "executed"
        assert result.execution_verified is False
        assert result.operation_id == "op-1"
        call = client.post.await_args
        assert call.args[0].endswith("/api/v1/proposals/decision-packages")
        assert call.kwargs["headers"]["Content-Type"] == "application/cloudevents+json"
        assert call.kwargs["headers"]["Idempotency-Key"] == signed.package.idempotency_id
        assert call.kwargs["headers"]["Authorization"] == "Bearer oidc-token"
        event = json.loads(call.kwargs["content"])
        assert event["specversion"] == "1.0"
        assert event["data"]["digest"] == signed.digest

    @pytest.mark.asyncio
    async def test_policy_rejection_stays_rejected(self):
        response = MagicMock()
        response.status_code = 403
        response.content = b'{"reason":"authority denied"}'
        response.json.return_value = {"reason": "authority denied"}
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.post = AsyncMock(return_value=response)

        with patch("gcl.adapter.proposer_adapter.httpx.AsyncClient", return_value=client):
            result = await ProposerAdapter(
                url="https://proposer.example.test",
            ).propose(_signed_package())

        assert result.status == "rejected"
        assert result.reason == "authority denied"
        assert result.execution_verified is False


class TestCommitterBoundary:
    @pytest.mark.asyncio
    async def test_surviving_decision_calls_proposer_and_never_actuator(self):
        adapter = MagicMock()
        adapter.propose = AsyncMock(return_value={
            "status": "accepted",
            "execution_verified": True,
        })
        adapter.actuate = AsyncMock()
        ledger = LedgerClient(url="")

        result = await Committer().commit(
            ActionStep(
                step_index=0,
                action_type="scale",
                parameters={"replicas": 4},
            ),
            FalsificationResult(
                action_id=_signed_package().package.package_id,
                verdict=Verdict.SURVIVES,
                reasoning="checks survived",
            ),
            adapter,
            ledger,
            "corr-boundary",
            decision_package=_signed_package(),
        )

        adapter.propose.assert_awaited_once()
        adapter.actuate.assert_not_called()
        assert result["committed"] is True
        assert result["proposal_response"]["execution_verified"] is False
        entries = await ledger.query_chain("corr-boundary")
        assert entries[-1]["entry_type"] == "gcl.decision_package.proposed"
        assert entries[-1]["content"]["execution_verified"] is False
