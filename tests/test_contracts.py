from uuid import uuid4

import pytest

from gcl.domain.contracts import (
    ActionPlan,
    ActionStep,
    Constraint,
    Evidence,
    FalsificationResult,
    LoopCycle,
    ObjectiveSpec,
    Trajectory,
    TrajectoryPoint,
)
from gcl.domain.enums import ConstraintSource, ConstraintType, Verdict
from tests.conftest import make_constraint, make_trajectory


class TestEvidence:
    def test_valid_construction(self):
        e = Evidence(metric="latency_ms", value=5000.0)
        assert e.metric == "latency_ms"
        assert e.value == 5000.0
        assert e.id is not None

    def test_serialization_roundtrip(self):
        e = Evidence(metric="cpu_pct", value=85.0, source="prometheus")
        data = e.model_dump()
        e2 = Evidence.model_validate(data)
        assert e2.metric == e.metric
        assert e2.value == e.value
        assert e2.id == e.id


class TestConstraint:
    def test_valid_construction(self):
        eid = uuid4()
        c = Constraint(
            type=ConstraintType.LATENCY,
            bound=5000.0,
            hard=True,
            justification_evidence_ids=[eid],
            confidence=0.9,
            source=ConstraintSource.DETERMINISTIC,
        )
        assert c.type == ConstraintType.LATENCY
        assert c.hard is True
        assert c.confidence == 0.9

    def test_empty_evidence_rejected(self):
        with pytest.raises(ValueError, match="justifying evidence"):
            Constraint(
                type=ConstraintType.LATENCY,
                bound=5000.0,
                hard=True,
                justification_evidence_ids=[],
                confidence=0.9,
                source=ConstraintSource.DETERMINISTIC,
            )

    def test_confidence_range(self):
        with pytest.raises(ValueError):
            make_constraint(confidence=1.5)
        with pytest.raises(ValueError):
            make_constraint(confidence=-0.1)

    def test_all_constraint_types(self):
        for ct in ConstraintType:
            c = make_constraint(ctype=ct)
            assert c.type == ct

    def test_serialization_roundtrip(self):
        c = make_constraint()
        data = c.model_dump()
        c2 = Constraint.model_validate(data)
        assert c2.id == c.id
        assert c2.type == c.type
        assert c2.bound == c.bound


class TestTrajectory:
    def test_valid_construction(self):
        t = make_trajectory()
        assert t.horizon_steps == 10
        assert len(t.points) == 10
        assert t.confidence == 0.8

    def test_empty_points_rejected(self):
        with pytest.raises(ValueError, match="at least one point"):
            Trajectory(points=[], horizon_steps=5, confidence=0.5)

    def test_confidence_range(self):
        with pytest.raises(ValueError):
            make_trajectory(confidence=1.1)

    def test_horizon_must_be_positive(self):
        with pytest.raises(ValueError):
            Trajectory(
                points=[TrajectoryPoint(step=0, value=1.0)],
                horizon_steps=0,
                confidence=0.5,
            )

    def test_serialization_roundtrip(self):
        t = make_trajectory()
        data = t.model_dump()
        t2 = Trajectory.model_validate(data)
        assert len(t2.points) == len(t.points)
        assert t2.confidence == t.confidence


class TestObjectiveSpec:
    def test_valid_construction(self):
        o = ObjectiveSpec(
            terms=["latency_cost"],
            weights=[1.0],
            hard_constraint_ids=[uuid4()],
            soft_constraint_ids=[],
            rationale="Focus on latency.",
        )
        assert len(o.terms) == 1
        assert o.weights == [1.0]

    def test_empty_terms_rejected(self):
        with pytest.raises(ValueError, match="at least one cost term"):
            ObjectiveSpec(
                terms=[],
                weights=[],
                hard_constraint_ids=[],
                soft_constraint_ids=[],
                rationale="No terms.",
            )

    def test_weights_length_mismatch(self):
        with pytest.raises(ValueError, match="weights length must match"):
            ObjectiveSpec(
                terms=["a", "b"],
                weights=[1.0],
                hard_constraint_ids=[],
                soft_constraint_ids=[],
                rationale="Mismatch.",
            )

    def test_serialization_roundtrip(self):
        o = ObjectiveSpec(
            terms=["a", "b"],
            weights=[0.6, 0.4],
            hard_constraint_ids=[uuid4()],
            soft_constraint_ids=[uuid4()],
            rationale="Balanced.",
        )
        data = o.model_dump()
        o2 = ObjectiveSpec.model_validate(data)
        assert o2.terms == o.terms
        assert o2.weights == o.weights


class TestActionPlan:
    def test_valid_construction(self):
        step = ActionStep(step_index=0, action_type="scale", parameters={"replicas": 5})
        plan = ActionPlan(steps=[step], committed_step_index=0, horizon_steps=1)
        assert plan.committed_step_index == 0
        assert len(plan.steps) == 1

    def test_committed_index_must_be_zero(self):
        steps = [
            ActionStep(step_index=i, action_type="no_action", parameters={})
            for i in range(3)
        ]
        with pytest.raises(ValueError, match="only the first step"):
            ActionPlan(steps=steps, committed_step_index=1, horizon_steps=3)

    def test_empty_steps_rejected(self):
        with pytest.raises(ValueError, match="at least one step"):
            ActionPlan(steps=[], committed_step_index=0, horizon_steps=1)

    def test_serialization_roundtrip(self):
        step = ActionStep(step_index=0, action_type="scale", parameters={"replicas": 3})
        plan = ActionPlan(steps=[step], committed_step_index=0, horizon_steps=1)
        data = plan.model_dump()
        plan2 = ActionPlan.model_validate(data)
        assert plan2.committed_step_index == plan.committed_step_index


class TestFalsificationResult:
    def test_survives(self):
        r = FalsificationResult(
            action_id=uuid4(),
            verdict=Verdict.SURVIVES,
            reasoning="All checks passed.",
        )
        assert r.verdict == Verdict.SURVIVES
        assert r.failed_check is None

    def test_fails_with_check(self):
        r = FalsificationResult(
            action_id=uuid4(),
            verdict=Verdict.FAILS,
            failed_check="capacity_overcommit",
            reasoning="Requested 20 replicas, max is 10.",
        )
        assert r.verdict == Verdict.FAILS
        assert r.failed_check == "capacity_overcommit"

    def test_serialization_roundtrip(self):
        r = FalsificationResult(
            action_id=uuid4(),
            verdict=Verdict.FAILS,
            failed_check="test",
            reasoning="reason",
            evidence_ids=[uuid4()],
        )
        data = r.model_dump()
        r2 = FalsificationResult.model_validate(data)
        assert r2.verdict == r.verdict
        assert r2.failed_check == r.failed_check


class TestLoopCycle:
    def test_valid_construction(self, sample_constraint, sample_trajectory, sample_objective):
        cycle = LoopCycle(
            constraints_snapshot=[sample_constraint],
            trajectory=sample_trajectory,
            objective=sample_objective,
            correlation_id="test-corr-001",
        )
        assert cycle.committed is False
        assert cycle.correlation_id == "test-corr-001"
        assert cycle.action_plan is None

    def test_serialization_roundtrip(self, sample_constraint, sample_trajectory, sample_objective):
        cycle = LoopCycle(
            constraints_snapshot=[sample_constraint],
            trajectory=sample_trajectory,
            objective=sample_objective,
            correlation_id="test-corr-002",
        )
        data = cycle.model_dump()
        cycle2 = LoopCycle.model_validate(data)
        assert cycle2.correlation_id == cycle.correlation_id
        assert len(cycle2.constraints_snapshot) == 1
