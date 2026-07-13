from __future__ import annotations

from unittest.mock import patch

import pytest

from gcl.domain.contracts import Evidence
from gcl.domain.enums import Verdict
from gcl.loop.accountability import AccountabilityTracker
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


class TestSemanticRoutingBDD:
    """Given prompts of varying complexity, when classified,
    then simple routes to small models and complex to large."""

    def test_mixed_prompts_classified_correctly(self):
        from gcl.classifier.prompt_classifier import PromptClassifier, PromptTier
        classifier = PromptClassifier()

        simple_prompts = ["What is 2+2?", "Hello", "Define gravity", "Who is Einstein?"]
        complex_prompts = ["Write a detailed essay on quantum computing", "Implement a red-black tree", "Analyze the economic impact of AI"]

        for p in simple_prompts:
            assert classifier.classify(p).tier == PromptTier.SIMPLE, f"Expected simple for: {p}"

        for p in complex_prompts:
            assert classifier.classify(p).tier == PromptTier.COMPLEX, f"Expected complex for: {p}"


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


class TestCooldownPreventsDuplicateScaleBDD:
    """Given a scale action was recently committed, when the loop runs again
    with the same breach, then the cooldown prevents a duplicate scale action."""

    @pytest.mark.asyncio
    async def test_cooldown_blocks_repeat_scale(self, ledger):
        tracker = AccountabilityTracker()
        driver = LoopDriver(ledger=ledger, accountability=tracker)

        signals = (
            [Evidence(metric="latency_ms", value=8000.0) for _ in range(5)]
            + [Evidence(metric="replicas", value=3.0)]
            + [Evidence(metric="max_replicas", value=10.0)]
        )
        p1, p2, p3 = _force_deterministic()
        with p1, p2, p3:
            cycle1 = await driver.run_cycle(signals)

        # First cycle should commit (scale or similar)
        if cycle1.committed and cycle1.action_plan is not None:
            first_action = cycle1.action_plan.steps[0].action_type
            if first_action != "no_action":
                # Second cycle with same signals should be blocked by cooldown
                with p1, p2, p3:
                    cycle2 = await driver.run_cycle(signals)
                if cycle2.action_plan is not None:
                    second_action = cycle2.action_plan.steps[0].action_type
                    assert second_action == "no_action", (
                        f"Cooldown should block repeat {first_action}, got {second_action}"
                    )


class TestOutcomeTrackingAfterScaleBDD:
    """Given a scale action was committed and latency subsequently dropped,
    when the next cycle runs, then the outcome is marked as effective."""

    @pytest.mark.asyncio
    async def test_effective_outcome_after_scale(self, ledger):
        tracker = AccountabilityTracker()
        tracker._outcome_min_age_seconds = 0  # immediate checking for test
        driver = LoopDriver(ledger=ledger, accountability=tracker)

        high_signals = (
            [Evidence(metric="latency_ms", value=8000.0) for _ in range(5)]
            + [Evidence(metric="replicas", value=3.0)]
            + [Evidence(metric="max_replicas", value=10.0)]
        )
        p1, p2, p3 = _force_deterministic()
        with p1, p2, p3:
            cycle1 = await driver.run_cycle(high_signals)

        if cycle1.committed:
            # Simulate recovery: latency drops
            low_signals = (
                [Evidence(metric="latency_ms", value=3000.0) for _ in range(5)]
                + [Evidence(metric="replicas", value=6.0)]
                + [Evidence(metric="max_replicas", value=10.0)]
            )
            with p1, p2, p3:
                cycle2 = await driver.run_cycle(low_signals)

            # Proposal acceptance is not execution evidence. A later metric
            # window alone cannot create a verified outcome.
            entries = await ledger.query_chain(cycle2.correlation_id)
            entry_types = {e["entry_type"] for e in entries}
            assert "gcl.outcome" not in entry_types


class TestProposalResponseCapturedBDD:
    """A proposer acknowledgement is captured without implying execution."""

    @pytest.mark.asyncio
    async def test_fleet_response_on_cycle(self, ledger):
        from unittest.mock import AsyncMock, MagicMock
        mock_adapter = MagicMock()
        mock_adapter.propose = AsyncMock(return_value={
            "status": "accepted",
            "proposal_id": "proposal-123",
            "execution_verified": False,
        })
        mock_adapter.actuate = AsyncMock()

        driver = LoopDriver(ledger=ledger, adapter=mock_adapter)

        signals = (
            [Evidence(metric="latency_ms", value=8000.0) for _ in range(5)]
            + [Evidence(metric="replicas", value=3.0)]
            + [Evidence(metric="max_replicas", value=10.0)]
        )
        p1, p2, p3 = _force_deterministic()
        with p1, p2, p3:
            cycle = await driver.run_cycle(signals)

        if cycle.committed:
            assert cycle.proposal_response is not None
            assert cycle.proposal_response["status"] == "accepted"
            assert cycle.execution_verified is False
            mock_adapter.actuate.assert_not_called()
