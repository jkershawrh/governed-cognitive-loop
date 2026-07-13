from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

import pytest

from gcl.domain.contracts import (
    ActionPlan,
    ActionStep,
    Constraint,
    Evidence,
    FalsificationResult,
    ObjectiveSpec,
    Trajectory,
    TrajectoryPoint,
)
from gcl.domain.enums import ConstraintSource, ConstraintType, Verdict
from gcl.config import get_settings


@pytest.fixture(autouse=True)
def deliberate_standalone_test_runtime(monkeypatch):
    """Tests opt in to the only fail-open runtime mode."""
    monkeypatch.setenv("GCL_RUNTIME_MODE", "standalone-test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def sample_evidence():
    return Evidence(
        metric="latency_ms",
        value=6000.0,
        timestamp=datetime(2025, 1, 15, 12, 0, 0),
    )


@pytest.fixture
def sample_evidence_list():
    e1 = Evidence(metric="latency_ms", value=6000.0)
    e2 = Evidence(metric="replicas", value=8.0)
    e3 = Evidence(metric="hourly_cost", value=500.0)
    return [e1, e2, e3]


@pytest.fixture
def sample_constraint(sample_evidence):
    return Constraint(
        type=ConstraintType.LATENCY,
        bound=5000.0,
        hard=True,
        justification_evidence_ids=[sample_evidence.id],
        confidence=0.9,
        source=ConstraintSource.DETERMINISTIC,
    )


@pytest.fixture
def sample_trajectory():
    points = [TrajectoryPoint(step=i, value=3000.0 + i * 200.0) for i in range(10)]
    return Trajectory(
        points=points,
        horizon_steps=10,
        confidence=0.8,
    )


@pytest.fixture
def sample_objective(sample_constraint):
    return ObjectiveSpec(
        terms=["latency_cost", "resource_cost"],
        weights=[0.8, 0.2],
        hard_constraint_ids=[sample_constraint.id],
        soft_constraint_ids=[],
        rationale="Latency breach detected, prioritizing latency reduction.",
    )


@pytest.fixture
def sample_action_step():
    return ActionStep(
        step_index=0,
        action_type="scale",
        parameters={"replicas": 5, "pool": "default"},
        predicted_effect={"latency_ms": 4000.0},
    )


@pytest.fixture
def sample_action_plan(sample_action_step):
    steps = [sample_action_step] + [
        ActionStep(
            step_index=i,
            action_type="no_action",
            parameters={},
        )
        for i in range(1, 10)
    ]
    return ActionPlan(steps=steps, committed_step_index=0, horizon_steps=10)


@pytest.fixture
def sample_falsification_survives(sample_action_step):
    return FalsificationResult(
        action_id=uuid4(),
        verdict=Verdict.SURVIVES,
        reasoning="All deterministic checks passed.",
        evidence_ids=[],
    )


@pytest.fixture
def sample_falsification_fails(sample_action_step):
    return FalsificationResult(
        action_id=uuid4(),
        verdict=Verdict.FAILS,
        failed_check="capacity_overcommit",
        reasoning="Action requests 20 replicas but pool max is 10.",
        evidence_ids=[],
    )


def make_evidence(metric: str = "latency_ms", value: float = 5000.0) -> Evidence:
    return Evidence(metric=metric, value=value)


def make_constraint(
    ctype: ConstraintType = ConstraintType.LATENCY,
    bound: float = 5000.0,
    hard: bool = True,
    evidence_ids: Optional[list] = None,
    confidence: float = 0.9,
    source: ConstraintSource = ConstraintSource.DETERMINISTIC,
) -> Constraint:
    if evidence_ids is None:
        evidence_ids = [uuid4()]
    return Constraint(
        type=ctype,
        bound=bound,
        hard=hard,
        justification_evidence_ids=evidence_ids,
        confidence=confidence,
        source=source,
    )


def make_trajectory(
    values: Optional[list] = None,
    horizon_steps: int = 10,
    confidence: float = 0.8,
) -> Trajectory:
    if values is None:
        values = [3000.0 + i * 200.0 for i in range(horizon_steps)]
    points = [TrajectoryPoint(step=i, value=v) for i, v in enumerate(values)]
    return Trajectory(points=points, horizon_steps=horizon_steps, confidence=confidence)
