from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from gcl.domain.contracts import ActionStep


class FleetIntent(BaseModel):
    type: str
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    horizon_seconds: int = Field(default=60, ge=0)
    justification: str = ""
    state_snapshot: dict = Field(default_factory=dict)
    pool: str = "default"


class ScaleIntent(FleetIntent):
    type: str = "scale"
    current_replicas: int = Field(default=0, ge=0)
    desired_replicas: int = Field(default=1, ge=0)
    metric: str = "latency_ms"


class PreWarmIntent(FleetIntent):
    type: str = "pre_warm"
    model: str = "default"
    target_replicas: int = Field(default=1, ge=1)


class ShedLoadIntent(FleetIntent):
    type: str = "shed_load"
    model: str = "default"
    max_inflight: int = Field(default=100, ge=0)
    duration_seconds: int = Field(default=300, ge=0)


class AlertIntent(FleetIntent):
    type: str = "alert"
    severity: str = "warning"
    message: str = ""
    recommended_action: str = ""


class MigrateIntent(FleetIntent):
    type: str = "migrate"
    source_pool: str = "default"
    target_pool: str = ""
    model: str = "default"
    reason: str = ""


class RollbackIntent(FleetIntent):
    type: str = "rollback"
    original_action: str = ""
    reason: str = ""


def map_action_to_intent(
    action_step: ActionStep, correlation_id: str = ""
) -> Optional[FleetIntent]:
    params = action_step.parameters
    justification = f"GCL cycle {correlation_id}: {action_step.action_type} action"

    if action_step.action_type == "scale":
        return ScaleIntent(
            justification=justification,
            pool=params.get("pool", "default"),
            current_replicas=int(params.get("current_replicas", 0)),
            desired_replicas=int(params.get("replicas", 1)),
            state_snapshot={"correlation_id": correlation_id},
        )

    if action_step.action_type == "pre_warm":
        return PreWarmIntent(
            justification=justification,
            pool=params.get("pool", "default"),
            target_replicas=int(params.get("target_replicas", 1)),
            model=str(params.get("model", "default")),
            state_snapshot={"correlation_id": correlation_id},
        )

    if action_step.action_type == "shed_load":
        return ShedLoadIntent(
            justification=justification,
            pool=params.get("pool", "default"),
            max_inflight=int(params.get("max_inflight", 100)),
            duration_seconds=int(params.get("duration_seconds", 300)),
            model=str(params.get("model", "default")),
            state_snapshot={"correlation_id": correlation_id},
        )

    if action_step.action_type == "alert":
        return AlertIntent(
            justification=justification,
            severity=str(params.get("severity", "warning")),
            message=str(params.get("message", "")),
            recommended_action=str(params.get("recommended_action", "")),
            state_snapshot={"correlation_id": correlation_id},
        )

    if action_step.action_type == "migrate":
        return MigrateIntent(
            justification=justification,
            source_pool=str(params.get("source_pool", "default")),
            target_pool=str(params.get("target_pool", "")),
            model=str(params.get("model", "default")),
            reason=str(params.get("reason", "")),
            state_snapshot={"correlation_id": correlation_id},
        )

    if action_step.action_type == "rollback":
        return RollbackIntent(
            justification=justification,
            original_action=str(params.get("original_action", "")),
            reason=str(params.get("reason", "")),
            state_snapshot={"correlation_id": correlation_id},
        )

    if action_step.action_type == "no_action":
        return None

    return None
