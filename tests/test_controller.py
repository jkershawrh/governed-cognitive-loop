from __future__ import annotations

import pytest
from uuid import uuid4

from gcl.controller.controller import Controller
from gcl.domain.contracts import (
    ActionPlan,
    Constraint,
    ObjectiveSpec,
    Trajectory,
    TrajectoryPoint,
)
from gcl.domain.enums import ConstraintSource, ConstraintType
from tests.conftest import make_constraint, make_trajectory


@pytest.fixture
def controller():
    return Controller()


def _make_objective(hard_ids=None, soft_ids=None):
    return ObjectiveSpec(
        terms=["latency_cost", "resource_cost"],
        weights=[0.8, 0.2],
        hard_constraint_ids=hard_ids or [],
        soft_constraint_ids=soft_ids or [],
        rationale="Latency-focused weighting.",
    )


def _breach_trajectory(breach_value=6000.0, horizon=10):
    points = [TrajectoryPoint(step=i, value=breach_value) for i in range(horizon)]
    return Trajectory(points=points, horizon_steps=horizon, confidence=0.8)


class TestController:
    def test_basic_optimization(self, controller):
        trajectory = _breach_trajectory(6000.0)
        latency_c = make_constraint(ctype=ConstraintType.LATENCY, bound=5000.0, hard=True)
        capacity_c = make_constraint(ctype=ConstraintType.CAPACITY, bound=10.0, hard=True)
        objective = _make_objective(hard_ids=[latency_c.id, capacity_c.id])

        result = controller.optimize(trajectory, objective, [latency_c, capacity_c])
        assert result is not None
        assert isinstance(result, ActionPlan)

    def test_committed_step_never_violates_hard_constraint(self, controller):
        trajectory = _breach_trajectory(6000.0)
        latency_c = make_constraint(ctype=ConstraintType.LATENCY, bound=5000.0, hard=True)
        capacity_c = make_constraint(ctype=ConstraintType.CAPACITY, bound=10.0, hard=True)
        objective = _make_objective(hard_ids=[latency_c.id, capacity_c.id])

        result = controller.optimize(trajectory, objective, [latency_c, capacity_c])
        if result is not None:
            committed = result.steps[result.committed_step_index]
            replicas = committed.parameters.get("replicas")
            if replicas is not None:
                assert replicas <= capacity_c.bound

    def test_infeasible_produces_shed_load(self, controller):
        """When capacity is totally exhausted, produce shed_load instead of None."""
        trajectory = _breach_trajectory(100000.0)
        latency_c = make_constraint(ctype=ConstraintType.LATENCY, bound=1.0, hard=True)
        capacity_c = make_constraint(ctype=ConstraintType.CAPACITY, bound=2.0, hard=True)
        objective = _make_objective(hard_ids=[latency_c.id, capacity_c.id])

        result = controller.optimize(trajectory, objective, [latency_c, capacity_c])
        assert result is not None
        committed = result.steps[result.committed_step_index]
        assert committed.action_type == "shed_load"

    def test_only_first_step_committed(self, controller):
        trajectory = _breach_trajectory(6000.0)
        latency_c = make_constraint(ctype=ConstraintType.LATENCY, bound=5000.0, hard=True)
        capacity_c = make_constraint(ctype=ConstraintType.CAPACITY, bound=20.0, hard=True)
        objective = _make_objective(hard_ids=[latency_c.id, capacity_c.id])

        result = controller.optimize(trajectory, objective, [latency_c, capacity_c])
        assert result is not None
        assert result.committed_step_index == 0

    def test_action_plan_length_matches_horizon(self, controller):
        for horizon in [5, 10, 15]:
            trajectory = _breach_trajectory(6000.0, horizon=horizon)
            latency_c = make_constraint(ctype=ConstraintType.LATENCY, bound=5000.0, hard=True)
            objective = _make_objective(hard_ids=[latency_c.id])

            result = controller.optimize(trajectory, objective, [latency_c])
            assert result is not None
            assert len(result.steps) == horizon

    def test_soft_constraints_can_be_violated(self, controller):
        trajectory = _breach_trajectory(6000.0)
        latency_c = make_constraint(ctype=ConstraintType.LATENCY, bound=5000.0, hard=True)
        budget_c = make_constraint(ctype=ConstraintType.BUDGET, bound=100.0, hard=False)
        objective = _make_objective(
            hard_ids=[latency_c.id],
            soft_ids=[budget_c.id],
        )

        result = controller.optimize(trajectory, objective, [latency_c, budget_c])
        assert result is not None

    def test_no_breach_produces_no_action(self, controller):
        points = [TrajectoryPoint(step=i, value=3000.0) for i in range(10)]
        trajectory = Trajectory(points=points, horizon_steps=10, confidence=0.9)
        latency_c = make_constraint(ctype=ConstraintType.LATENCY, bound=5000.0, hard=True)
        objective = _make_objective(hard_ids=[latency_c.id])

        result = controller.optimize(trajectory, objective, [latency_c])
        assert result is not None
        committed = result.steps[0]
        assert committed.action_type == "no_action"

    def test_shed_load_when_capacity_exhausted(self, controller):
        """When latency is breached and capacity is exhausted, produce shed_load."""
        trajectory = _breach_trajectory(6000.0)
        latency_c = make_constraint(ctype=ConstraintType.LATENCY, bound=5000.0, hard=True)
        capacity_c = make_constraint(ctype=ConstraintType.CAPACITY, bound=1.0, hard=True)
        objective = _make_objective(hard_ids=[latency_c.id, capacity_c.id])

        result = controller.optimize(trajectory, objective, [latency_c, capacity_c])
        assert result is not None, "Should produce shed_load instead of returning None"
        committed = result.steps[result.committed_step_index]
        assert committed.action_type == "shed_load"

    def test_alert_on_compliance_violation(self, controller):
        """When a hard COMPLIANCE constraint is active, produce alert."""
        trajectory = _breach_trajectory(3000.0)
        compliance_c = make_constraint(ctype=ConstraintType.COMPLIANCE, bound=1.0, hard=True)
        objective = _make_objective(hard_ids=[compliance_c.id])

        result = controller.optimize(trajectory, objective, [compliance_c])
        assert result is not None
        committed = result.steps[result.committed_step_index]
        assert committed.action_type == "alert"

    def test_compliance_blocks_scale(self, controller):
        """When both COMPLIANCE and LATENCY are hard, committed step must NOT be scale."""
        trajectory = _breach_trajectory(6000.0)
        latency_c = make_constraint(ctype=ConstraintType.LATENCY, bound=5000.0, hard=True)
        compliance_c = make_constraint(ctype=ConstraintType.COMPLIANCE, bound=1.0, hard=True)
        objective = _make_objective(hard_ids=[latency_c.id, compliance_c.id])

        result = controller.optimize(trajectory, objective, [latency_c, compliance_c])
        assert result is not None
        committed = result.steps[result.committed_step_index]
        assert committed.action_type != "scale"

    def test_shed_load_has_valid_parameters(self, controller):
        """shed_load action should have max_inflight > 0 and duration_seconds > 0."""
        trajectory = _breach_trajectory(6000.0)
        latency_c = make_constraint(ctype=ConstraintType.LATENCY, bound=5000.0, hard=True)
        capacity_c = make_constraint(ctype=ConstraintType.CAPACITY, bound=1.0, hard=True)
        objective = _make_objective(hard_ids=[latency_c.id, capacity_c.id])

        result = controller.optimize(trajectory, objective, [latency_c, capacity_c])
        assert result is not None
        committed = result.steps[result.committed_step_index]
        if committed.action_type == "shed_load":
            assert committed.parameters.get("max_inflight", 0) > 0
            assert committed.parameters.get("duration_seconds", 0) > 0

    def test_scale_capped_at_max_replicas(self, controller):
        """Extreme latency should not produce replicas beyond capacity bound."""
        trajectory = _breach_trajectory(1000000.0)  # 1M ms latency
        latency_c = make_constraint(ctype=ConstraintType.LATENCY, bound=5000.0, hard=True)
        capacity_c = make_constraint(ctype=ConstraintType.CAPACITY, bound=10.0, hard=True)
        objective = _make_objective(hard_ids=[latency_c.id, capacity_c.id])
        result = controller.optimize(trajectory, objective, [latency_c, capacity_c])
        if result is not None:
            committed = result.steps[result.committed_step_index]
            replicas = committed.parameters.get("replicas")
            if replicas is not None:
                assert replicas <= 10, f"replicas={replicas} exceeds capacity bound of 10"

    def test_scale_capped_at_config_max(self, controller):
        """Without capacity constraint, scale should still be bounded by config."""
        trajectory = _breach_trajectory(50000.0)
        latency_c = make_constraint(ctype=ConstraintType.LATENCY, bound=5000.0, hard=True)
        objective = _make_objective(hard_ids=[latency_c.id])
        result = controller.optimize(trajectory, objective, [latency_c])
        if result is not None:
            committed = result.steps[result.committed_step_index]
            replicas = committed.parameters.get("replicas")
            if replicas is not None:
                from gcl.config import get_settings
                assert replicas <= get_settings().max_scale_replicas, f"replicas={replicas} exceeds config max"

    def test_shed_load_when_max_replicas_zero(self, controller):
        """max_replicas=0 with latency breach should produce shed_load, not None."""
        trajectory = _breach_trajectory(8000.0)
        latency_c = make_constraint(ctype=ConstraintType.LATENCY, bound=5000.0, hard=True)
        capacity_c = make_constraint(ctype=ConstraintType.CAPACITY, bound=0.0, hard=True)
        objective = _make_objective(hard_ids=[latency_c.id, capacity_c.id])
        result = controller.optimize(trajectory, objective, [latency_c, capacity_c])
        assert result is not None, "Should produce shed_load, not None"
        committed = result.steps[result.committed_step_index]
        assert committed.action_type == "shed_load", f"Expected shed_load, got {committed.action_type}"

    def test_migrate_on_compliance_plus_capacity_exhaustion(self, controller):
        """Compliance + capacity exhaustion should produce migrate."""
        trajectory = _breach_trajectory(3000.0)
        compliance_c = make_constraint(ctype=ConstraintType.COMPLIANCE, bound=1.0, hard=True)
        capacity_c = make_constraint(ctype=ConstraintType.CAPACITY, bound=0.0, hard=True)
        objective = _make_objective(hard_ids=[compliance_c.id, capacity_c.id])
        result = controller.optimize(trajectory, objective, [compliance_c, capacity_c])
        assert result is not None
        committed = result.steps[result.committed_step_index]
        assert committed.action_type == "migrate"

    def test_alert_on_compliance_without_capacity_exhaustion(self, controller):
        """Compliance alone (no capacity pressure) should produce alert."""
        trajectory = _breach_trajectory(3000.0)
        compliance_c = make_constraint(ctype=ConstraintType.COMPLIANCE, bound=1.0, hard=True)
        capacity_c = make_constraint(ctype=ConstraintType.CAPACITY, bound=10.0, hard=True)
        objective = _make_objective(hard_ids=[compliance_c.id, capacity_c.id])
        result = controller.optimize(trajectory, objective, [compliance_c, capacity_c])
        assert result is not None
        committed = result.steps[result.committed_step_index]
        assert committed.action_type == "alert"

    def test_no_optimality_claim(self):
        import inspect
        source = inspect.getsource(Controller)
        lower = source.lower()
        for word in ["optimal", "optimality"]:
            if word in lower:
                context = lower[lower.index(word) - 20 : lower.index(word) + 30]
                assert "not claim" in context or "does not" in context or "no " in context, (
                    f"Controller source contains '{word}' without disclaimer"
                )
