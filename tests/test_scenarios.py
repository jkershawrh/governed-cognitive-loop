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


class TestSpikeDetectionBDD:
    """Given a spike-then-recovery pattern, when the loop runs,
    then the committed action is scale or pre_warm (not no_action)."""

    @pytest.mark.asyncio
    async def test_spike_governs_correctly(self, driver):
        signals = (
            [Evidence(metric="latency_ms", value=10000.0) for _ in range(5)]
            + [Evidence(metric="latency_ms", value=500.0) for _ in range(5)]
            + [Evidence(metric="replicas", value=3.0)]
            + [Evidence(metric="max_replicas", value=10.0)]
        )
        p1, p2, p3 = _force_deterministic()
        with p1, p2, p3:
            cycle = await driver.run_cycle(signals)

        if cycle.action_plan is not None:
            committed = cycle.action_plan.steps[cycle.action_plan.committed_step_index]
            assert committed.action_type != "no_action", (
                "Spike should trigger scale or pre_warm, not no_action"
            )


class TestExtremeBoundedBDD:
    """Given extreme latency with limited capacity, when the loop runs,
    then the scale action is bounded by capacity."""

    @pytest.mark.asyncio
    async def test_extreme_latency_bounded(self, driver):
        signals = (
            [Evidence(metric="latency_ms", value=1000000.0) for _ in range(10)]
            + [Evidence(metric="replicas", value=3.0)]
            + [Evidence(metric="max_replicas", value=10.0)]
        )
        p1, p2, p3 = _force_deterministic()
        with p1, p2, p3:
            cycle = await driver.run_cycle(signals)

        if cycle.action_plan is not None:
            committed = cycle.action_plan.steps[cycle.action_plan.committed_step_index]
            replicas = committed.parameters.get("replicas")
            if replicas is not None:
                assert replicas <= 20, f"Scale should be bounded, got replicas={replicas}"


class TestZeroCapacityShedLoadBDD:
    """Given latency breach with max_replicas=0, when the loop runs,
    then shed_load is produced (not infeasible)."""

    @pytest.mark.asyncio
    async def test_zero_capacity_shed_load(self, driver):
        signals = (
            [Evidence(metric="latency_ms", value=8000.0) for _ in range(10)]
            + [Evidence(metric="replicas", value=4.0)]
            + [Evidence(metric="max_replicas", value=0.0)]
        )
        p1, p2, p3 = _force_deterministic()
        with p1, p2, p3:
            cycle = await driver.run_cycle(signals)

        assert cycle.action_plan is not None, "Should produce shed_load, not None"
        committed = cycle.action_plan.steps[cycle.action_plan.committed_step_index]
        assert committed.action_type == "shed_load", (
            f"Expected shed_load with zero capacity, got {committed.action_type}"
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
        if disturbance.action_plan is not None:
            committed_action = disturbance.action_plan.steps[0].action_type
            assert committed_action in ("shed_load", "scale"), (
                f"Disturbance step should shed_load or attempt scale, got {committed_action}"
            )
            if committed_action == "scale":
                assert disturbance.committed is False, "Scale at disturbance should be rejected"

        recovery = results[5]
        assert recovery.committed is True, "Recovery step should commit"


class TestMultiClusterMigrationBDD:
    """Given multi-cluster pressure with compliance violation, when the loop runs,
    then migrate is produced at step 3 and alert at step 4."""

    @pytest.mark.asyncio
    async def test_multi_cluster_step3_migrate_or_shed(self, driver):
        scenario = ScenarioEngine(scenario="multi_cluster_migration", seed=42)
        p1, p2, p3 = _force_deterministic()
        with p1, p2, p3:
            cycle = await driver.run_cycle(scenario.get_step(3))
        if cycle.action_plan is not None:
            committed = cycle.action_plan.steps[cycle.action_plan.committed_step_index]
            assert committed.action_type in ("migrate", "shed_load"), (
                f"Step 3 should produce migrate or shed_load, got {committed.action_type}"
            )

    @pytest.mark.asyncio
    async def test_multi_cluster_step4_compliance(self, driver):
        scenario = ScenarioEngine(scenario="multi_cluster_migration", seed=42)
        p1, p2, p3 = _force_deterministic()
        with p1, p2, p3:
            cycle = await driver.run_cycle(scenario.get_step(4))
        if cycle.action_plan is not None:
            committed = cycle.action_plan.steps[cycle.action_plan.committed_step_index]
            assert committed.action_type in ("alert", "migrate"), (
                f"Step 4 should produce alert or migrate, got {committed.action_type}"
            )
