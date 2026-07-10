from __future__ import annotations

from typing import Optional

import numpy as np

from gcl.config import get_settings
from gcl.domain.contracts import Constraint, TrajectoryPoint
from gcl.domain.enums import ConstraintType


def compute_action_for_step(
    point: TrajectoryPoint,
    hard_constraints: list[Constraint],
    soft_constraints: list[Constraint],
    weights: dict[str, float],
) -> Optional[dict]:
    """Compute action parameters for a single horizon step.

    Returns action parameters dict, or None if infeasible.
    """
    action_type = "no_action"
    parameters: dict = {}

    compliance_bounds = [c for c in hard_constraints if c.type == ConstraintType.COMPLIANCE]
    capacity_bounds = [c for c in hard_constraints if c.type == ConstraintType.CAPACITY]
    latency_bounds = [c for c in hard_constraints if c.type == ConstraintType.LATENCY]

    # Compliance constraints take priority over latency.
    if compliance_bounds:
        action_type = "alert"
        parameters = {
            "severity": "critical",
            "message": "Compliance constraint active",
            "recommended_action": "migrate workloads",
        }
        return {"action_type": action_type, "parameters": parameters}

    max_replicas = None
    for c in capacity_bounds:
        if max_replicas is None or c.bound < max_replicas:
            max_replicas = c.bound

    latency_target = None
    for c in latency_bounds:
        if latency_target is None or c.bound < latency_target:
            latency_target = c.bound

    if latency_target is not None and point.value > latency_target:
        overshoot_ratio = point.value / latency_target
        desired_scale = int(np.ceil(overshoot_ratio))
        settings = get_settings()
        config_max = settings.max_scale_replicas
        desired_scale = min(desired_scale, config_max)

        if max_replicas is not None and desired_scale > max_replicas:
            if not _can_satisfy_with_alternatives(point, hard_constraints, max_replicas):
                # Capacity exhausted: shed load instead of returning None.
                action_type = "shed_load"
                parameters = {
                    "max_inflight": 50,
                    "duration_seconds": 300,
                    "model": "default",
                    "pool": "default",
                }
                return {"action_type": action_type, "parameters": parameters}
            desired_scale = int(max_replicas)

        action_type = "scale"
        parameters = {"replicas": desired_scale, "pool": "default"}

    elif latency_target is not None and point.value > latency_target * 0.8:
        action_type = "pre_warm"
        parameters = {"target_replicas": 2, "pool": "default"}

    if action_type == "no_action":
        parameters = {}

    return {"action_type": action_type, "parameters": parameters}


def _can_satisfy_with_alternatives(
    point: TrajectoryPoint,
    hard_constraints: list[Constraint],
    max_replicas: float,
) -> bool:
    if max_replicas <= 0:
        return False

    latency_target = None
    for c in hard_constraints:
        if c.type == ConstraintType.LATENCY:
            if latency_target is None or c.bound < latency_target:
                latency_target = c.bound

    if latency_target is None:
        return True

    estimated_latency_at_max = point.value / max_replicas
    return estimated_latency_at_max <= latency_target


def check_hard_constraint_satisfaction(
    action_params: dict,
    hard_constraints: list[Constraint],
) -> bool:
    """Verify the action does not violate any hard constraint."""
    action_type = action_params.get("action_type", "")
    replicas = action_params.get("parameters", {}).get("replicas")
    target_replicas = action_params.get("parameters", {}).get("target_replicas")

    # If any hard compliance constraint exists, reject scale and pre_warm.
    compliance_active = any(c.type == ConstraintType.COMPLIANCE for c in hard_constraints)
    if compliance_active and action_type in ("scale", "pre_warm"):
        return False

    for c in hard_constraints:
        if c.type == ConstraintType.CAPACITY:
            if replicas is not None and replicas > c.bound:
                return False
            if target_replicas is not None and target_replicas > c.bound:
                return False

    return True
