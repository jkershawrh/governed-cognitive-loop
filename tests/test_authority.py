from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from gcl.loop.authority import CONSEQUENCE_SCORES, collect_agent_promotion_attestation


class TestOptionalAgentPromotionCompatibility:
    @pytest.mark.asyncio
    async def test_missing_service_produces_no_attestation(self):
        with patch("gcl.loop.authority.get_settings") as settings:
            settings.return_value.agent_promotion_url = ""
            result = await collect_agent_promotion_attestation("scale", "decision-1")

        assert result is None

    @pytest.mark.asyncio
    async def test_refusal_is_returned_as_metadata(self):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "verdict": "refuse",
            "reason": "above optional ceiling",
            "consequence_score": 0.5,
            "ceiling": 0.2,
        }
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.post = AsyncMock(return_value=response)

        with (
            patch("gcl.loop.authority.get_settings") as settings,
            patch("gcl.loop.authority.httpx.AsyncClient", return_value=client),
        ):
            settings.return_value.agent_promotion_url = "http://promotion.test"
            settings.return_value.agent_promotion_bearer_token = "token"
            settings.return_value.proposer_agent_id = "gcl"
            result = await collect_agent_promotion_attestation("scale", "decision-1")

        assert result is not None
        assert result["verdict"] == "refuse"
        assert result["ceiling"] == 0.2
        assert client.post.await_args.kwargs["headers"] == {
            "Authorization": "Bearer token"
        }

    @pytest.mark.asyncio
    async def test_unavailable_service_is_non_authoritative_metadata(self):
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.post = AsyncMock(side_effect=httpx.ConnectError("offline"))

        with (
            patch("gcl.loop.authority.get_settings") as settings,
            patch("gcl.loop.authority.httpx.AsyncClient", return_value=client),
        ):
            settings.return_value.agent_promotion_url = "http://promotion.test"
            settings.return_value.agent_promotion_bearer_token = ""
            settings.return_value.proposer_agent_id = "gcl"
            result = await collect_agent_promotion_attestation("migrate", "decision-2")

        assert result is not None
        assert result["verdict"] == "unavailable"
        assert result["consequence_score"] == CONSEQUENCE_SCORES["migrate"]

    def test_consequence_scores_are_advisory_and_bounded(self):
        assert CONSEQUENCE_SCORES["no_action"] == 0.0
        assert CONSEQUENCE_SCORES["scale"] > CONSEQUENCE_SCORES["pre_warm"]
        assert all(0.0 <= score <= 1.0 for score in CONSEQUENCE_SCORES.values())
