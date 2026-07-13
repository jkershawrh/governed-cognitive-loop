from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gcl.loop.authority import check_authority, CONSEQUENCE_SCORES


class TestAuthorityGate:
    @pytest.mark.asyncio
    async def test_allow_when_not_configured(self):
        with patch("gcl.loop.authority.get_settings") as mock:
            mock.return_value.authority_url = ""
            mock.return_value.runtime_mode = "standalone-test"
            result = await check_authority("scale", "test-id")
        assert result["verdict"] == "allow"

    @pytest.mark.asyncio
    async def test_refuse_when_not_configured_in_production(self):
        with patch("gcl.loop.authority.get_settings") as mock:
            mock.return_value.authority_url = ""
            mock.return_value.runtime_mode = "production"
            result = await check_authority("scale", "test-id")
        assert result["verdict"] == "refuse"

    @pytest.mark.asyncio
    async def test_allow_when_service_unavailable(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("timeout"))

        with patch("gcl.loop.authority.get_settings") as mock_settings:
            mock_settings.return_value.authority_url = "http://fake:8080"
            mock_settings.return_value.authority_agent_id = "gcl"
            mock_settings.return_value.runtime_mode = "standalone-test"
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await check_authority("scale", "test-id")
        assert result["verdict"] == "allow"

    @pytest.mark.asyncio
    async def test_refuse_when_service_unavailable_in_production(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("timeout"))

        with patch("gcl.loop.authority.get_settings") as mock_settings:
            mock_settings.return_value.authority_url = "http://fake:8080"
            mock_settings.return_value.authority_agent_id = "gcl"
            mock_settings.return_value.runtime_mode = "production"
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await check_authority("scale", "test-id")
        assert result["verdict"] == "refuse"
        assert "fail-closed" in result["reason"]

    @pytest.mark.asyncio
    async def test_refuse_when_above_ceiling(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "verdict": "refuse",
            "reason": "consequence 0.5 exceeds ceiling 0.2",
            "ceiling": 0.2,
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("gcl.loop.authority.get_settings") as mock_settings:
            mock_settings.return_value.authority_url = "http://fake:8080"
            mock_settings.return_value.authority_agent_id = "gcl"
            mock_settings.return_value.runtime_mode = "production"
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await check_authority("scale", "test-id")
        assert result["verdict"] == "refuse"

    @pytest.mark.asyncio
    async def test_route_human_for_probation(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "verdict": "route_human",
            "reason": "T0 (PROBATION): all actions route to human",
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("gcl.loop.authority.get_settings") as mock_settings:
            mock_settings.return_value.authority_url = "http://fake:8080"
            mock_settings.return_value.authority_agent_id = "gcl"
            mock_settings.return_value.runtime_mode = "production"
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await check_authority("scale", "test-id")
        assert result["verdict"] == "route_human"

    def test_consequence_scores_defined(self):
        for action in ["no_action", "pre_warm", "alert", "scale", "shed_load", "migrate", "rollback"]:
            assert action in CONSEQUENCE_SCORES
        assert CONSEQUENCE_SCORES["no_action"] == 0.0
        assert CONSEQUENCE_SCORES["scale"] > CONSEQUENCE_SCORES["pre_warm"]
        assert CONSEQUENCE_SCORES["migrate"] > CONSEQUENCE_SCORES["scale"]

    def test_consequence_scores_ordered(self):
        scores = list(CONSEQUENCE_SCORES.values())
        assert CONSEQUENCE_SCORES["no_action"] < CONSEQUENCE_SCORES["shed_load"]
