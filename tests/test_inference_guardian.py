from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import json

import pytest

from gcl.inference.client import InferenceResult, _validate_with_guardian


class TestGuardianValidation:
    @pytest.mark.asyncio
    async def test_guardian_blocks_action_response(self):
        """Guardian returns allowed=false for responses containing action fields."""
        result = InferenceResult(
            text='{"action_type": "scale", "replicas": 5}',
            model="test",
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"allowed": False, "reason": "action_type field blocked"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch.dict("os.environ", {"GUARDIAN_URL": "http://localhost:8081"}):
            with patch("httpx.AsyncClient", return_value=mock_client):
                validated = await _validate_with_guardian(result)

        assert validated is None

    @pytest.mark.asyncio
    async def test_guardian_allows_objective_response(self):
        """Guardian returns allowed=true for valid ObjectiveSpec responses."""
        result = InferenceResult(
            text='{"terms": ["latency_cost"], "weights": [1.0], "rationale": "Focus on latency."}',
            model="test",
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"allowed": True}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch.dict("os.environ", {"GUARDIAN_URL": "http://localhost:8081"}):
            with patch("httpx.AsyncClient", return_value=mock_client):
                validated = await _validate_with_guardian(result)

        assert validated is not None
        assert validated.text == result.text

    @pytest.mark.asyncio
    async def test_guardian_unavailable_falls_through(self):
        """When GUARDIAN_URL is not set, responses pass through."""
        result = InferenceResult(
            text='{"action_type": "scale"}',
            model="test",
        )
        with patch.dict("os.environ", {}, clear=True):
            validated = await _validate_with_guardian(result)

        assert validated is not None
        assert validated.text == result.text

    @pytest.mark.asyncio
    async def test_guardian_timeout_falls_through(self):
        """When Guardian times out, responses pass through (fail-open)."""
        result = InferenceResult(
            text='{"terms": ["latency_cost"]}',
            model="test",
        )
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("timeout"))

        with patch.dict("os.environ", {"GUARDIAN_URL": "http://localhost:8081"}):
            with patch("httpx.AsyncClient", return_value=mock_client):
                validated = await _validate_with_guardian(result)

        assert validated is not None

    @pytest.mark.asyncio
    async def test_guardian_non_json_response_passes(self):
        """Non-JSON LLM responses are wrapped and pass through Guardian."""
        result = InferenceResult(
            text="This is a plain text response with no JSON.",
            model="test",
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"allowed": True}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch.dict("os.environ", {"GUARDIAN_URL": "http://localhost:8081"}):
            with patch("httpx.AsyncClient", return_value=mock_client):
                validated = await _validate_with_guardian(result)

        assert validated is not None
