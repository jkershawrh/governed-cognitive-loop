from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from gcl.domain.contracts import (
    ActionStep,
    Constraint,
    Evidence,
    Trajectory,
    TrajectoryPoint,
)
from gcl.domain.enums import ConstraintSource, ConstraintType, Verdict
from gcl.falsification.gate import FalsificationGate
from tests.conftest import make_constraint, make_trajectory


@pytest.fixture
def gate():
    return FalsificationGate()


def _scale_action(replicas=5):
    return ActionStep(
        step_index=0,
        action_type="scale",
        parameters={"replicas": replicas, "pool": "default"},
    )


def _prewarm_action(assumed_warmup=5):
    return ActionStep(
        step_index=0,
        action_type="pre_warm",
        parameters={"target_replicas": 2, "assumed_warmup_seconds": assumed_warmup},
    )


def _no_action():
    return ActionStep(step_index=0, action_type="no_action", parameters={})


class TestFalsificationGate:
    @pytest.mark.asyncio
    async def test_known_bad_action_rejected(self, gate):
        action = _scale_action(replicas=20)
        trajectory = make_trajectory(confidence=0.8)
        capacity_c = make_constraint(ctype=ConstraintType.CAPACITY, bound=10.0, hard=True)
        evidence = [Evidence(metric="max_replicas", value=10.0)]

        with patch("gcl.falsification.gate.get_force_rules", return_value=True):
            result = await gate.falsify(action, trajectory, [capacity_c], evidence)

        assert result.verdict == Verdict.FAILS
        assert result.failed_check == "capacity_overcommit"

    @pytest.mark.asyncio
    async def test_sound_action_survives(self, gate):
        action = _scale_action(replicas=5)
        trajectory = make_trajectory(confidence=0.8)
        capacity_c = make_constraint(ctype=ConstraintType.CAPACITY, bound=10.0, hard=True)
        evidence = [Evidence(metric="latency_ms", value=6000.0)]

        with patch("gcl.falsification.gate.get_force_rules", return_value=True):
            result = await gate.falsify(action, trajectory, [capacity_c], evidence)

        assert result.verdict == Verdict.SURVIVES

    @pytest.mark.asyncio
    async def test_low_confidence_prediction_rejected(self, gate):
        action = _scale_action(replicas=5)
        trajectory = make_trajectory(confidence=0.2)
        evidence = [Evidence(metric="latency_ms", value=6000.0)]

        with patch("gcl.falsification.gate.get_force_rules", return_value=True):
            result = await gate.falsify(action, trajectory, [], evidence)

        assert result.verdict == Verdict.FAILS
        assert result.failed_check == "low_prediction_confidence"

    @pytest.mark.asyncio
    async def test_capacity_overcommit_rejected(self, gate):
        action = _scale_action(replicas=15)
        trajectory = make_trajectory(confidence=0.8)
        evidence = [Evidence(metric="max_replicas", value=10.0)]

        with patch("gcl.falsification.gate.get_force_rules", return_value=True):
            result = await gate.falsify(action, trajectory, [], evidence)

        assert result.verdict == Verdict.FAILS
        assert "capacity_overcommit" in result.failed_check

    @pytest.mark.asyncio
    async def test_warmup_time_unrealistic_rejected(self, gate):
        action = _prewarm_action(assumed_warmup=5)
        trajectory = make_trajectory(confidence=0.8)
        evidence = [Evidence(metric="warmup_seconds", value=30.0)]

        with patch("gcl.falsification.gate.get_force_rules", return_value=True):
            result = await gate.falsify(action, trajectory, [], evidence)

        assert result.verdict == Verdict.FAILS
        assert result.failed_check == "warmup_time_unrealistic"

    @pytest.mark.asyncio
    async def test_deterministic_checks_run_before_llm(self, gate):
        action = _scale_action(replicas=20)
        trajectory = make_trajectory(confidence=0.8)
        capacity_c = make_constraint(ctype=ConstraintType.CAPACITY, bound=10.0, hard=True)
        evidence = [Evidence(metric="max_replicas", value=10.0)]

        mock_probe = AsyncMock(return_value=None)
        gate._adversary.probe = mock_probe

        with patch("gcl.falsification.gate.get_force_rules", return_value=False):
            result = await gate.falsify(action, trajectory, [capacity_c], evidence)

        assert result.verdict == Verdict.FAILS
        mock_probe.assert_not_called()

    @pytest.mark.asyncio
    async def test_failed_check_named_in_result(self, gate):
        action = _scale_action(replicas=20)
        trajectory = make_trajectory(confidence=0.8)
        capacity_c = make_constraint(ctype=ConstraintType.CAPACITY, bound=10.0, hard=True)
        evidence = []

        with patch("gcl.falsification.gate.get_force_rules", return_value=True):
            result = await gate.falsify(action, trajectory, [capacity_c], evidence)

        assert result.verdict == Verdict.FAILS
        assert result.failed_check is not None
        assert len(result.failed_check) > 0

    @pytest.mark.asyncio
    async def test_no_action_survives(self, gate):
        action = _no_action()
        trajectory = make_trajectory(confidence=0.8)
        evidence = [Evidence(metric="latency_ms", value=3000.0)]

        with patch("gcl.falsification.gate.get_force_rules", return_value=True):
            result = await gate.falsify(action, trajectory, [], evidence)

        assert result.verdict == Verdict.SURVIVES

    @pytest.mark.asyncio
    async def test_llm_adversary_can_reject(self, gate):
        action = _scale_action(replicas=5)
        trajectory = make_trajectory(confidence=0.8)
        evidence = [Evidence(metric="latency_ms", value=6000.0)]

        gate._adversary.probe = AsyncMock(return_value="Cascading failure risk detected.")

        with patch("gcl.falsification.gate.get_force_rules", return_value=False):
            result = await gate.falsify(action, trajectory, [], evidence)

        assert result.verdict == Verdict.FAILS
        assert result.failed_check == "llm_adversarial_probe"

    @pytest.mark.asyncio
    async def test_compliance_rejects_scale(self, gate):
        """scale action + hard compliance constraint -> fails with compliance_action_invalid."""
        action = _scale_action(replicas=5)
        trajectory = make_trajectory(confidence=0.8)
        compliance_c = make_constraint(ctype=ConstraintType.COMPLIANCE, bound=1.0, hard=True)
        evidence = [Evidence(metric="latency_ms", value=6000.0)]

        with patch("gcl.falsification.gate.get_force_rules", return_value=True):
            result = await gate.falsify(action, trajectory, [compliance_c], evidence)

        assert result.verdict == Verdict.FAILS
        assert result.failed_check == "compliance_action_invalid"

    @pytest.mark.asyncio
    async def test_shed_load_bounded_rejects_extreme(self, gate):
        """shed_load with duration=999999 -> fails."""
        action = ActionStep(
            step_index=0,
            action_type="shed_load",
            parameters={"max_inflight": 50, "duration_seconds": 999999},
        )
        trajectory = make_trajectory(confidence=0.8)
        evidence = [Evidence(metric="latency_ms", value=6000.0)]

        with patch("gcl.falsification.gate.get_force_rules", return_value=True):
            result = await gate.falsify(action, trajectory, [], evidence)

        assert result.verdict == Verdict.FAILS

    @pytest.mark.asyncio
    async def test_valid_shed_load_survives(self, gate):
        """shed_load with max_inflight=50, duration=300 -> survives (no compliance constraint)."""
        action = ActionStep(
            step_index=0,
            action_type="shed_load",
            parameters={"max_inflight": 50, "duration_seconds": 300},
        )
        trajectory = make_trajectory(confidence=0.8)
        evidence = [Evidence(metric="latency_ms", value=6000.0)]

        with patch("gcl.falsification.gate.get_force_rules", return_value=True):
            result = await gate.falsify(action, trajectory, [], evidence)

        assert result.verdict == Verdict.SURVIVES

    @pytest.mark.asyncio
    async def test_evidence_ids_in_result(self, gate):
        action = _scale_action(replicas=5)
        trajectory = make_trajectory(confidence=0.8)
        evidence = [
            Evidence(metric="latency_ms", value=6000.0),
            Evidence(metric="cpu_pct", value=80.0),
        ]

        with patch("gcl.falsification.gate.get_force_rules", return_value=True):
            result = await gate.falsify(action, trajectory, [], evidence)

        assert len(result.evidence_ids) == 2
