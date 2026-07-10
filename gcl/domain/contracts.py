from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from gcl.domain.enums import ConstraintSource, ConstraintType, Verdict


class Evidence(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    metric: str
    value: float
    timestamp: datetime = Field(default_factory=datetime.now)
    source: str = "system"
    labels: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class Constraint(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: ConstraintType
    bound: float
    hard: bool
    justification_evidence_ids: list[UUID]
    confidence: float = Field(ge=0.0, le=1.0)
    source: ConstraintSource

    @field_validator("justification_evidence_ids")
    @classmethod
    def must_have_evidence(cls, v: list[UUID]) -> list[UUID]:
        if not v:
            raise ValueError("constraint must carry at least one justifying evidence id")
        return v


class TrajectoryPoint(BaseModel):
    step: int
    value: float
    lower: Optional[float] = None
    upper: Optional[float] = None


class Trajectory(BaseModel):
    points: list[TrajectoryPoint]
    horizon_steps: int = Field(gt=0)
    confidence: float = Field(ge=0.0, le=1.0)
    generated_at: datetime = Field(default_factory=datetime.now)

    @field_validator("points")
    @classmethod
    def points_not_empty(cls, v: list[TrajectoryPoint]) -> list[TrajectoryPoint]:
        if not v:
            raise ValueError("trajectory must have at least one point")
        return v


class ObjectiveSpec(BaseModel):
    terms: list[str]
    weights: list[float]
    hard_constraint_ids: list[UUID]
    soft_constraint_ids: list[UUID]
    rationale: str

    @field_validator("terms")
    @classmethod
    def terms_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("objective must have at least one cost term")
        return v

    @field_validator("weights")
    @classmethod
    def weights_match_terms(cls, v: list[float], info) -> list[float]:
        terms = info.data.get("terms")
        if terms is not None and len(v) != len(terms):
            raise ValueError("weights length must match terms length")
        return v


class ActionStep(BaseModel):
    step_index: int = Field(ge=0)
    action_type: str
    parameters: dict
    predicted_effect: dict = Field(default_factory=dict)


class ActionPlan(BaseModel):
    steps: list[ActionStep]
    committed_step_index: int = Field(ge=0)
    horizon_steps: int = Field(gt=0)

    @field_validator("steps")
    @classmethod
    def steps_not_empty(cls, v: list[ActionStep]) -> list[ActionStep]:
        if not v:
            raise ValueError("action plan must have at least one step")
        return v

    @field_validator("committed_step_index")
    @classmethod
    def committed_index_is_zero(cls, v: int) -> int:
        if v != 0:
            raise ValueError("receding horizon: only the first step (index 0) may be committed")
        return v


class FalsificationResult(BaseModel):
    action_id: UUID
    verdict: Verdict
    failed_check: Optional[str] = None
    reasoning: str
    evidence_ids: list[UUID] = Field(default_factory=list)


class LoopCycle(BaseModel):
    cycle_id: UUID = Field(default_factory=uuid4)
    constraints_snapshot: list[Constraint]
    trajectory: Trajectory
    objective: ObjectiveSpec
    action_plan: Optional[ActionPlan] = None
    falsification: Optional[FalsificationResult] = None
    committed: bool = False
    correlation_id: str
