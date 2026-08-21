"""Production gating of destructive endpoints, and adversary participation.

Two behaviours are pinned here.

The production gate already covered /cycle, /cycle/metrics and
/classify-and-run so that production ingestion must arrive as a signed
DeepField CloudEvent. /reset and /scenario/seed were outside it, which meant
a production instance would erase its own decision record, or accept
synthetic scenario state, for any caller that could reach it.

Separately, a SURVIVES verdict used to read identically whether the LLM
adversary examined the action and found nothing or never ran at all. The
falsification record now states which happened.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from gcl.api.app import create_app
from gcl.config import get_settings
from gcl.domain.contracts import ActionStep, Evidence
from gcl.domain.enums import AdversaryStatus, Verdict
from gcl.falsification.gate import FalsificationGate
from tests.conftest import make_trajectory


@pytest.fixture
def client():
    return TestClient(create_app())


def _production(monkeypatch):
    monkeypatch.setenv("GCL_RUNTIME_MODE", "production")
    get_settings.cache_clear()


def _standalone(monkeypatch):
    monkeypatch.setenv("GCL_RUNTIME_MODE", "standalone-test")
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _restore_settings():
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/api/v1/reset", None),
        ("/api/v1/scenario/seed", {"scenario": "inference_fleet_spike", "seed": 42}),
    ],
)
def test_destructive_endpoints_refused_in_production(monkeypatch, client, path, payload):
    _production(monkeypatch)
    response = client.post(path, json=payload) if payload else client.post(path)
    assert response.status_code == 403, response.text
    assert "development compatibility endpoint" in response.text


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/api/v1/reset", None),
        ("/api/v1/scenario/seed", {"scenario": "inference_fleet_spike", "seed": 42}),
    ],
)
def test_destructive_endpoints_available_outside_production(
    monkeypatch, client, path, payload
):
    _standalone(monkeypatch)
    response = client.post(path, json=payload) if payload else client.post(path)
    assert response.status_code == 200, response.text


class TestAdversaryStatusIsRecorded:
    @pytest.fixture
    def gate(self):
        return FalsificationGate()

    def _sound_action(self):
        return ActionStep(
            step_index=0,
            action_type="scale",
            parameters={"replicas": 5, "pool": "default"},
        )

    @pytest.mark.asyncio
    async def test_rules_mode_is_distinguishable_from_a_clean_probe(self, gate):
        """The case the old record could not express."""
        evidence = [Evidence(metric="latency_ms", value=6000.0)]
        with patch("gcl.falsification.gate.get_force_rules", return_value=True):
            result = await gate.falsify(
                self._sound_action(), make_trajectory(confidence=0.8), [], evidence
            )
        assert result.verdict == Verdict.SURVIVES
        assert result.adversary_status == AdversaryStatus.SKIPPED_RULES_MODE
        assert "skipped" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_clean_probe_is_recorded_as_probed(self, gate):
        evidence = [Evidence(metric="latency_ms", value=6000.0)]
        gate._adversary.probe = AsyncMock(return_value=(None, AdversaryStatus.PROBED))
        with patch("gcl.falsification.gate.get_force_rules", return_value=False):
            result = await gate.falsify(
                self._sound_action(), make_trajectory(confidence=0.8), [], evidence
            )
        assert result.verdict == Verdict.SURVIVES
        assert result.adversary_status == AdversaryStatus.PROBED
        assert "no objection" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_unavailable_adversary_is_not_reported_as_a_clean_pass(self, gate):
        evidence = [Evidence(metric="latency_ms", value=6000.0)]
        gate._adversary.probe = AsyncMock(
            return_value=(None, AdversaryStatus.UNAVAILABLE)
        )
        with patch("gcl.falsification.gate.get_force_rules", return_value=False):
            result = await gate.falsify(
                self._sound_action(), make_trajectory(confidence=0.8), [], evidence
            )
        assert result.verdict == Verdict.SURVIVES
        assert result.adversary_status == AdversaryStatus.UNAVAILABLE
        assert "unavailable" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_deterministic_failure_records_not_reached(self, gate):
        """A deterministic check fired first, so the adversary was never called."""
        evidence = [Evidence(metric="max_replicas", value=10.0)]
        action = ActionStep(
            step_index=0,
            action_type="scale",
            parameters={"replicas": 20, "pool": "default"},
        )
        with patch("gcl.falsification.gate.get_force_rules", return_value=True):
            result = await gate.falsify(
                action, make_trajectory(confidence=0.8), [], evidence
            )
        assert result.verdict == Verdict.FAILS
        assert result.adversary_status == AdversaryStatus.NOT_REACHED
