from __future__ import annotations

from typing import Optional

from gcl.domain.contracts import ActionStep, Constraint, Evidence, Trajectory
from gcl.domain.enums import ConstraintType
from gcl.config import get_settings


def check_capacity_available(
    action_step: ActionStep,
    evidence: list[Evidence],
    constraints: list[Constraint],
) -> Optional[str]:
    """Does the action assume capacity the evidence says is unavailable?"""
    replicas = action_step.parameters.get("replicas")
    target_replicas = action_step.parameters.get("target_replicas")
    requested = replicas or target_replicas
    if requested is None:
        return None

    for c in constraints:
        if c.type == ConstraintType.CAPACITY and c.hard:
            if requested > c.bound:
                return (
                    f"capacity_overcommit: action requests {requested} "
                    f"but hard capacity bound is {c.bound}"
                )

    for e in evidence:
        if e.metric == "max_replicas" and requested > e.value:
            return (
                f"capacity_overcommit: action requests {requested} "
                f"but evidence shows max_replicas={e.value}"
            )

    return None


def check_warmup_time_realistic(
    action_step: ActionStep,
    evidence: list[Evidence],
) -> Optional[str]:
    """Does the action assume a warm-up time the pool is not meeting?"""
    if action_step.action_type not in ("pre_warm", "scale"):
        return None

    assumed_warmup = action_step.parameters.get("assumed_warmup_seconds")
    if assumed_warmup is None:
        return None

    settings = get_settings()
    for e in evidence:
        if e.metric == "warmup_seconds":
            actual = e.value * settings.warmup_time_multiplier
            if assumed_warmup < actual:
                return (
                    f"warmup_time_unrealistic: action assumes {assumed_warmup}s warmup "
                    f"but evidence shows {e.value}s (with {settings.warmup_time_multiplier}x safety: {actual}s)"
                )

    return None


def check_prediction_confidence(
    action_step: ActionStep,
    trajectory: Trajectory,
) -> Optional[str]:
    """Does the action depend on a prediction whose confidence is below threshold?"""
    settings = get_settings()
    if trajectory.confidence < settings.falsification_confidence_floor:
        return (
            f"low_prediction_confidence: trajectory confidence is {trajectory.confidence}, "
            f"below floor of {settings.falsification_confidence_floor}"
        )
    return None


def check_compliance_action_valid(
    action_step: ActionStep,
    evidence: list[Evidence],
    constraints: list[Constraint],
) -> Optional[str]:
    """If any hard compliance constraint exists and action is scale/pre_warm, reject it."""
    compliance_active = any(
        c.type == ConstraintType.COMPLIANCE and c.hard for c in constraints
    )
    if compliance_active and action_step.action_type in ("scale", "pre_warm"):
        return "compliance_action_invalid: scaling does not fix a compliance problem"
    return None


def check_shed_load_bounded(
    action_step: ActionStep,
    evidence: list[Evidence],
    constraints: list[Constraint],
) -> Optional[str]:
    """If action is shed_load, verify max_inflight > 0 and 0 < duration_seconds <= 3600."""
    if action_step.action_type != "shed_load":
        return None
    max_inflight = action_step.parameters.get("max_inflight", 0)
    duration = action_step.parameters.get("duration_seconds", 0)
    if max_inflight <= 0:
        return "shed_load_unbounded: max_inflight must be greater than 0"
    if duration <= 0 or duration > 3600:
        return f"shed_load_unbounded: duration_seconds={duration} out of valid range (1-3600)"
    return None


def check_scale_magnitude_reasonable(
    action_step: ActionStep,
    evidence: list[Evidence],
    constraints: list[Constraint],
) -> Optional[str]:
    """Reject scale actions that request more replicas than the configured max."""
    if action_step.action_type != "scale":
        return None
    replicas = action_step.parameters.get("replicas")
    if replicas is None:
        return None
    settings = get_settings()
    if replicas > settings.max_scale_replicas:
        return (
            f"scale_magnitude_unreasonable: scale requests {replicas} replicas, "
            f"exceeds configured maximum of {settings.max_scale_replicas}"
        )
    return None


def check_migration_target_available(
    action_step: ActionStep,
    evidence: list[Evidence],
    constraints: list[Constraint],
) -> Optional[str]:
    """If action is migrate, verify target_pool is not empty."""
    if action_step.action_type != "migrate":
        return None
    target_pool = action_step.parameters.get("target_pool", "")
    if not target_pool:
        return "migration_target_missing: migrate action has no target_pool specified"
    return None


ALL_CHECKS = [
    ("capacity_available", check_capacity_available),
    ("warmup_time_realistic", check_warmup_time_realistic),
    ("prediction_confidence", check_prediction_confidence),
    ("compliance_action_valid", check_compliance_action_valid),
    ("shed_load_bounded", check_shed_load_bounded),
    ("migration_target_available", check_migration_target_available),
]
