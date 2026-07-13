from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gcl.loop.passport import verify_passport, ACTION_SCOPES


class TestPassportVerification:
    @pytest.mark.asyncio
    async def test_passport_allow_when_not_configured(self):
        with patch("gcl.loop.passport.get_settings") as mock:
            mock.return_value.passport_url = ""
            mock.return_value.passport_id = ""
            result = await verify_passport("scale")
        assert result["decision"] == "ALLOW"

    @pytest.mark.asyncio
    async def test_passport_allow_when_scoped(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "decision": "ALLOW",
            "matched_scope": {"action_class": "fleet.*", "resource_pattern": "fleet-llm-d/*"},
            "passport_status": "ACTIVE",
        }
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("gcl.loop.passport.get_settings") as mock_settings:
            mock_settings.return_value.passport_url = "http://fake:8443"
            mock_settings.return_value.passport_id = "passport-123"
            mock_settings.return_value.authority_agent_id = "gcl"
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await verify_passport("scale")
        assert result["decision"] == "ALLOW"

    @pytest.mark.asyncio
    async def test_passport_deny_when_out_of_scope(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "decision": "DENY",
            "reason": "action_class fleet.migrate not in passport scope",
            "passport_status": "ACTIVE",
        }
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("gcl.loop.passport.get_settings") as mock_settings:
            mock_settings.return_value.passport_url = "http://fake:8443"
            mock_settings.return_value.passport_id = "passport-123"
            mock_settings.return_value.authority_agent_id = "gcl"
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await verify_passport("migrate")
        assert result["decision"] == "DENY"

    @pytest.mark.asyncio
    async def test_passport_unavailable_fails_open(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("timeout"))

        with patch("gcl.loop.passport.get_settings") as mock_settings:
            mock_settings.return_value.passport_url = "http://fake:8443"
            mock_settings.return_value.passport_id = "passport-123"
            mock_settings.return_value.authority_agent_id = "gcl"
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await verify_passport("scale")
        assert result["decision"] == "ALLOW"

    def test_all_action_types_have_scopes(self):
        for action in ["no_action", "pre_warm", "scale", "shed_load", "alert", "migrate", "rollback"]:
            assert action in ACTION_SCOPES
            assert ACTION_SCOPES[action].startswith("fleet.")
