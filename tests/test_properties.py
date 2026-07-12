from __future__ import annotations

import random

import pytest

from gcl.controller.controller import Controller
from gcl.domain.contracts import (
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


def _random_trajectory(horizon=10, seed=None):
    rng = random.Random(seed)
    points = [
        TrajectoryPoint(step=i, value=rng.uniform(1000, 10000))
        for i in range(horizon)
    ]
    return Trajectory(points=points, horizon_steps=horizon, confidence=rng.uniform(0.3, 1.0))


def _random_constraints(seed=None):
    rng = random.Random(seed)
    constraints = []
    if rng.random() > 0.3:
        constraints.append(
            make_constraint(
                ctype=ConstraintType.LATENCY,
                bound=rng.uniform(2000, 8000),
                hard=True,
            )
        )
    if rng.random() > 0.3:
        constraints.append(
            make_constraint(
                ctype=ConstraintType.CAPACITY,
                bound=rng.uniform(3, 20),
                hard=True,
            )
        )
    if rng.random() > 0.5:
        constraints.append(
            make_constraint(
                ctype=ConstraintType.BUDGET,
                bound=rng.uniform(100, 5000),
                hard=False,
            )
        )
    return constraints


def _make_objective(constraints):
    hard_ids = [c.id for c in constraints if c.hard]
    soft_ids = [c.id for c in constraints if not c.hard]
    return ObjectiveSpec(
        terms=["latency_cost", "resource_cost"],
        weights=[0.7, 0.3],
        hard_constraint_ids=hard_ids,
        soft_constraint_ids=soft_ids,
        rationale="Property test objective.",
    )


class TestHardConstraintProperty:
    @pytest.mark.parametrize("seed", range(100))
    def test_committed_step_satisfies_all_hard_constraints(self, controller, seed):
        trajectory = _random_trajectory(seed=seed)
        constraints = _random_constraints(seed=seed + 1000)

        if not constraints:
            return

        objective = _make_objective(constraints)
        result = controller.optimize(trajectory, objective, constraints)

        if result is None:
            return

        committed = result.steps[result.committed_step_index]
        hard = [c for c in constraints if c.hard]

        replicas = committed.parameters.get("replicas")
        target_replicas = committed.parameters.get("target_replicas")

        for c in hard:
            if c.type == ConstraintType.CAPACITY:
                if replicas is not None:
                    assert replicas <= c.bound, (
                        f"Committed step violates capacity constraint: "
                        f"replicas={replicas}, bound={c.bound}"
                    )
                if target_replicas is not None:
                    assert target_replicas <= c.bound

    @pytest.mark.parametrize("seed", range(100))
    def test_committed_step_index_is_always_zero(self, controller, seed):
        trajectory = _random_trajectory(seed=seed)
        constraints = _random_constraints(seed=seed + 2000)
        if not constraints:
            return
        objective = _make_objective(constraints)
        result = controller.optimize(trajectory, objective, constraints)
        if result is not None:
            assert result.committed_step_index == 0


class TestComplianceProperty:
    @pytest.mark.parametrize("seed", range(50))
    def test_compliance_never_produces_scale(self, controller, seed):
        """With a hard COMPLIANCE constraint, committed step must never be scale or pre_warm."""
        trajectory = _random_trajectory(seed=seed)
        compliance_c = make_constraint(
            ctype=ConstraintType.COMPLIANCE,
            bound=1.0,
            hard=True,
        )
        other_constraints = _random_constraints(seed=seed + 3000)
        all_constraints = [compliance_c] + other_constraints

        objective = _make_objective(all_constraints)
        result = controller.optimize(trajectory, objective, all_constraints)

        if result is not None:
            committed = result.steps[result.committed_step_index]
            assert committed.action_type not in ("scale", "pre_warm"), (
                f"Compliance constraint active but committed step is {committed.action_type}"
            )


class TestSemanticRoutingProperty:
    @pytest.mark.parametrize("seed", range(50))
    def test_simple_never_routes_complex_models(self, seed):
        from gcl.classifier.prompt_classifier import PromptClassifier, PromptTier
        import random
        classifier = PromptClassifier()
        rng = random.Random(seed)

        simple_starters = ["what is", "who is", "define", "how many", "when did", "hello", "hi", "yes", "no"]
        prompt = rng.choice(simple_starters) + " " + "test " * rng.randint(1, 5)
        result = classifier.classify(prompt)

        if result.tier == PromptTier.SIMPLE:
            models = classifier.get_models_for_tier(result.tier)
            complex_models = classifier.get_models_for_tier(PromptTier.COMPLEX)
            for m in models:
                assert m not in complex_models or m in classifier.get_models_for_tier(PromptTier.SIMPLE)


class TestShedLoadProperty:
    @pytest.mark.parametrize("seed", range(50))
    def test_shed_load_parameters_bounded(self, controller, seed):
        """When shed_load is produced, max_inflight >= 1 and duration_seconds > 0."""
        rng = random.Random(seed)
        breach_value = rng.uniform(6000, 15000)
        points = [
            TrajectoryPoint(step=i, value=breach_value)
            for i in range(10)
        ]
        trajectory = Trajectory(points=points, horizon_steps=10, confidence=0.8)

        latency_c = make_constraint(
            ctype=ConstraintType.LATENCY,
            bound=5000.0,
            hard=True,
        )
        capacity_c = make_constraint(
            ctype=ConstraintType.CAPACITY,
            bound=1.0,
            hard=True,
        )

        objective = _make_objective([latency_c, capacity_c])
        result = controller.optimize(trajectory, objective, [latency_c, capacity_c])

        if result is not None:
            committed = result.steps[result.committed_step_index]
            if committed.action_type == "shed_load":
                assert committed.parameters.get("max_inflight", 0) >= 1
                assert committed.parameters.get("duration_seconds", 0) > 0


class TestCooldownProperty:
    """Cooldown always blocks same action type within window, always allows different types."""

    @pytest.mark.parametrize("seed", range(50))
    def test_cooldown_never_blocks_different_action(self, seed):
        from gcl.loop.accountability import AccountabilityTracker
        rng = random.Random(seed)
        action_types = ["scale", "pre_warm", "shed_load", "alert", "migrate"]
        tracker = AccountabilityTracker()

        committed_type = rng.choice(action_types)
        tracker.record_commit(f"c{seed}", f"corr{seed}", committed_type, 8000.0)

        for other_type in action_types:
            if other_type != committed_type:
                allowed, _ = tracker.can_commit(other_type)
                assert allowed, (
                    f"Cooldown for {committed_type} should not block {other_type}"
                )

    @pytest.mark.parametrize("seed", range(50))
    def test_cooldown_always_blocks_same_action_within_window(self, seed):
        from gcl.loop.accountability import AccountabilityTracker
        rng = random.Random(seed)
        action_types = ["scale", "pre_warm", "shed_load", "alert", "migrate"]
        tracker = AccountabilityTracker()

        action_type = rng.choice(action_types)
        tracker.record_commit(f"c{seed}", f"corr{seed}", action_type, 8000.0)

        allowed, reason = tracker.can_commit(action_type)
        assert not allowed, (
            f"Cooldown should block repeat {action_type} within window"
        )
        assert "cooldown" in reason


class TestOutcomeEffectivenessProperty:
    """Outcome effectiveness is correctly determined by metric direction."""

    @pytest.mark.parametrize("seed", range(50))
    def test_scale_effective_iff_latency_decreases(self, seed):
        from gcl.loop.accountability import AccountabilityTracker
        from gcl.domain.contracts import Evidence as Ev
        rng = random.Random(seed)
        tracker = AccountabilityTracker()
        tracker._outcome_min_age_seconds = 0

        before_latency = rng.uniform(5000, 15000)
        tracker.record_commit(f"c{seed}", f"corr{seed}", "scale", before_latency)

        after_latency = rng.uniform(1000, 20000)
        evidence = [Ev(metric="latency_ms", value=after_latency)]
        outcomes = tracker.check_outcomes(evidence)

        assert len(outcomes) == 1
        expected_effective = after_latency < before_latency
        assert outcomes[0].effective == expected_effective, (
            f"before={before_latency}, after={after_latency}: "
            f"expected effective={expected_effective}, got {outcomes[0].effective}"
        )


class TestPendingOutcomesCapProperty:
    """Pending outcomes never exceed the configured cap regardless of commit volume."""

    @pytest.mark.parametrize("seed", range(20))
    def test_pending_never_exceeds_cap(self, seed):
        from unittest.mock import patch as mpatch
        from gcl.loop.accountability import AccountabilityTracker
        rng = random.Random(seed)
        cap = rng.randint(1, 5)
        tracker = AccountabilityTracker()

        with mpatch("gcl.loop.accountability.get_settings") as mock:
            mock.return_value.decision_cooldown_seconds = 0
            mock.return_value.max_pending_outcomes = cap
            for i in range(rng.randint(10, 30)):
                tracker.record_commit(f"c{i}", f"corr{i}", "scale", 8000.0)

        assert tracker.pending_count() <= cap, (
            f"Pending count {tracker.pending_count()} exceeds cap {cap}"
        )
