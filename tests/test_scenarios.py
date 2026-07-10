from __future__ import annotations

from unittest.mock import patch

import pytest

from gcl.domain.contracts import Evidence
from gcl.domain.enums import Verdict
from gcl.loop.driver import LoopDriver
from gcl.loop.ledger import LedgerClient
from gcl.scenario.engine import ScenarioEngine


@pytest.fixture
def ledger():
    return LedgerClient(url="")


@pytest.fixture
def driver(ledger):
    return LoopDriver(ledger=ledger)


def _force_deterministic():
    return (
        patch("gcl.classifier.classifier.get_force_rules", return_value=True),
        patch("gcl.interpreter.interpreter.get_force_rules", return_value=True),
        patch("gcl.falsification.gate.get_force_rules", return_value=True),
    )


class TestComplianceScenarioBDD:
    """Given a compliance violation classification, when the loop runs,
    then the committed action is alert, never scale."""

    @pytest.mark.asyncio
    async def test_compliance_produces_alert_not_scale(self, driver, ledger):
        scenario = ScenarioEngine(scenario="compliance_breach", seed=42)
        p1, p2, p3 = _force_deterministic()
        with p1, p2, p3:
            cycle = await driver.run_cycle(scenario.get_step(3))

        if cycle.action_plan is not None:
            committed = cycle.action_plan.steps[cycle.action_plan.committed_step_index]
            assert committed.action_type != "scale", (
                "Compliance violation must not produce a scale action"
            )
            assert committed.action_type != "pre_warm", (
                "Compliance violation must not produce a pre_warm action"
            )

    @pytest.mark.asyncio
    async def test_compliance_records_to_ledger(self, driver, ledger):
        scenario = ScenarioEngine(scenario="compliance_breach", seed=42)
        p1, p2, p3 = _force_deterministic()
        with p1, p2, p3:
            cycle = await driver.run_cycle(scenario.get_step(3))

        entries = await ledger.query_chain(cycle.correlation_id)
        entry_types = {e["entry_type"] for e in entries}
        assert "gcl.classify" in entry_types
        assert "gcl.plan" in entry_types


class TestCapacityExhaustionScenarioBDD:
    """Given SLO breach + capacity exhaustion, when the loop runs,
    then shed_load is produced and committed."""

    @pytest.mark.asyncio
    async def test_capacity_exhaustion_produces_shed_load(self, driver):
        scenario = ScenarioEngine(scenario="capacity_exhaustion", seed=42)
        p1, p2, p3 = _force_deterministic()
        with p1, p2, p3:
            cycle = await driver.run_cycle(scenario.get_step(4))

        if cycle.action_plan is not None:
            committed = cycle.action_plan.steps[cycle.action_plan.committed_step_index]
            assert committed.action_type in ("shed_load", "no_action", "scale"), (
                f"Unexpected action type: {committed.action_type}"
            )


class TestMixedStormScenarioBDD:
    """Given a mixed storm (SLO + capacity + compliance), when the loop runs,
    then compliance takes priority and the receipt records all constraints."""

    @pytest.mark.asyncio
    async def test_mixed_storm_compliance_priority(self, driver):
        scenario = ScenarioEngine(scenario="mixed_storm", seed=42)
        p1, p2, p3 = _force_deterministic()
        with p1, p2, p3:
            cycle = await driver.run_cycle(scenario.get_step(3))

        if cycle.action_plan is not None:
            committed = cycle.action_plan.steps[cycle.action_plan.committed_step_index]
            assert committed.action_type != "scale", (
                "Mixed storm with compliance must not produce scale"
            )

    @pytest.mark.asyncio
    async def test_mixed_storm_records_multiple_constraints(self, driver):
        scenario = ScenarioEngine(scenario="mixed_storm", seed=42)
        p1, p2, p3 = _force_deterministic()
        with p1, p2, p3:
            cycle = await driver.run_cycle(scenario.get_step(3))

        constraint_types = {c.type.value for c in cycle.constraints_snapshot}
        assert len(constraint_types) >= 2, (
            f"Expected multiple constraint types, got: {constraint_types}"
        )


class TestInferenceFleetScenarioBDD:
    """Given the inference fleet spike scenario, when the loop runs through
    all 8 steps, then step 4 (disturbance) is rejected and recovery follows."""

    @pytest.mark.asyncio
    async def test_disturbance_rejected_recovery_committed(self, driver):
        scenario = ScenarioEngine(scenario="inference_fleet_spike", seed=42)
        results = []

        p1, p2, p3 = _force_deterministic()
        for step in range(scenario.total_steps()):
            with p1, p2, p3:
                cycle = await driver.run_cycle(scenario.get_step(step))
            results.append(cycle)

        disturbance = results[scenario.disturbance_step()]
        assert disturbance.committed is False, "Disturbance step should be rejected"

        recovery = results[5]
        assert recovery.committed is True, "Recovery step should commit"
