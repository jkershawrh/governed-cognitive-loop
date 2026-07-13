from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from gcl.domain.contracts import (
    ActionPlan,
    Constraint,
    Evidence,
    FalsificationResult,
    Trajectory,
)


SCHEMA_VERSION = "gcl.llm-d.ai/decision-package/v1"
SCHEMA_URI = "https://schemas.llm-d.ai/gcl/decision-package/v1/schema.json"
CLOUD_EVENT_SCHEMA_URI = (
    "https://schemas.llm-d.ai/gcl/decision-package-cloudevent/v1/schema.json"
)
DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"
ACTION_CLASS_NAMES: dict[str, str] = {
    "deploy": "fleet.deploy",
    "scale": "fleet.scale",
    "route": "fleet.route",
    "pre_warm": "fleet.prewarm",
    "shed_load": "fleet.shed_load",
    "migrate": "fleet.migrate",
    "kv_transfer": "fleet.kv_transfer",
}
CanonicalFleetActionClass = Literal[
    "fleet.deploy",
    "fleet.scale",
    "fleet.route",
    "fleet.prewarm",
    "fleet.shed_load",
    "fleet.migrate",
    "fleet.kv_transfer",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return value.astimezone(timezone.utc)


def canonical_json(value: BaseModel | dict[str, Any]) -> bytes:
    """Return the contract's deterministic UTF-8 JSON representation."""
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", by_alias=True)
    else:
        payload = value
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_ref(value: BaseModel | dict[str, Any] | bytes | str) -> str:
    if isinstance(value, bytes):
        payload = value
    elif isinstance(value, str):
        payload = value.encode("utf-8")
    else:
        payload = canonical_json(value)
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DecisionConstraint(ContractModel):
    constraint_id: str = Field(min_length=1, max_length=256)
    constraint_type: str = Field(min_length=1, max_length=128)
    hard: bool
    bound: float
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(min_length=1)

    @field_validator("evidence_refs")
    @classmethod
    def validate_evidence_refs(cls, values: list[str]) -> list[str]:
        for value in values:
            if not re.fullmatch(DIGEST_PATTERN, value):
                raise ValueError(
                    "evidence references must be sha256:<64 lowercase hex>"
                )
        return values


class DecisionCandidate(ContractModel):
    candidate_id: str = Field(min_length=1, max_length=256)
    action_class: CanonicalFleetActionClass
    parameters: dict[str, Any]
    predicted_effect: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)


class RejectedAlternative(ContractModel):
    candidate: DecisionCandidate
    reason_code: str = Field(min_length=1, max_length=128)
    reasoning: str = Field(min_length=1, max_length=4096)


class DecisionFalsificationResult(ContractModel):
    candidate_id: str = Field(min_length=1, max_length=256)
    check_id: str = Field(min_length=1, max_length=256)
    verdict: Literal["survives", "fails"]
    reasoning: str = Field(min_length=1, max_length=4096)
    evidence_refs: list[str] = Field(min_length=1)

    @field_validator("evidence_refs")
    @classmethod
    def validate_evidence_refs(cls, values: list[str]) -> list[str]:
        for value in values:
            if not re.fullmatch(DIGEST_PATTERN, value):
                raise ValueError(
                    "evidence references must be sha256:<64 lowercase hex>"
                )
        return values


class ProposerIdentity(ContractModel):
    agent_id: str = Field(min_length=1, max_length=256)
    workload_identity: str = Field(
        pattern=r"^spiffe://[a-z0-9.-]+(?:/[A-Za-z0-9._~!$&'()*+,;=:@%-]+)*$"
    )
    trust_domain: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")


class AgentPromotionCompatibilityAttestation(ContractModel):
    """Optional proposer-ceiling provenance, never execution authority."""

    provider: Literal["agent-promotion"] = "agent-promotion"
    non_authoritative: Literal[True] = True
    subject: str = Field(min_length=1, max_length=256)
    action_class: CanonicalFleetActionClass
    decision: Literal["allow", "refuse", "route_human", "unavailable"]
    consequence_score: float = Field(ge=0.0, le=1.0)
    autonomy_ceiling: float = Field(ge=0.0, le=1.0)
    attestation_ref: str = Field(pattern=DIGEST_PATTERN)
    issued_at: datetime
    expires_at: datetime

    @field_validator("issued_at", "expires_at")
    @classmethod
    def timestamps_must_be_aware(cls, value: datetime, info) -> datetime:
        return _require_aware(value, info.field_name)

    @model_validator(mode="after")
    def expiry_follows_issue(self) -> "AgentPromotionCompatibilityAttestation":
        if self.expires_at <= self.issued_at:
            raise ValueError("compatibility attestation must expire after it is issued")
        return self


class DecisionPackageV1(ContractModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    package_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=_utc_now)
    expires_at: datetime
    correlation_id: str = Field(min_length=1, max_length=256)
    causation_id: str = Field(min_length=1, max_length=256)
    idempotency_id: str = Field(min_length=1, max_length=256)
    tenant: str = Field(min_length=1, max_length=256)
    zone: str = Field(min_length=1, max_length=256)
    proposer: ProposerIdentity
    agent_promotion: Optional[AgentPromotionCompatibilityAttestation] = None
    constraints: list[DecisionConstraint] = Field(min_length=1)
    candidates: list[DecisionCandidate] = Field(min_length=1)
    selected_candidate_id: str = Field(min_length=1, max_length=256)
    rejected_alternatives: list[RejectedAlternative]
    falsification_results: list[DecisionFalsificationResult] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_sources: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)

    @field_validator("created_at", "expires_at")
    @classmethod
    def timestamps_must_be_aware(cls, value: datetime, info) -> datetime:
        return _require_aware(value, info.field_name)

    @field_validator("evidence_refs")
    @classmethod
    def validate_evidence_refs(cls, values: list[str]) -> list[str]:
        for value in values:
            if not re.fullmatch(DIGEST_PATTERN, value):
                raise ValueError(
                    "evidence references must be sha256:<64 lowercase hex>"
                )
        if len(values) != len(set(values)):
            raise ValueError("evidence references must be unique")
        return values

    @model_validator(mode="after")
    def validate_references_and_expiry(self) -> "DecisionPackageV1":
        if self.expires_at <= self.created_at:
            raise ValueError("decision package must expire after it is created")
        if (
            self.agent_promotion is not None
            and self.agent_promotion.expires_at <= self.created_at
        ):
            raise ValueError(
                "agent-promotion compatibility attestation is already expired"
            )
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate ids must be unique")
        if self.selected_candidate_id not in candidate_ids:
            raise ValueError("selected_candidate_id must reference a candidate")
        for result in self.falsification_results:
            if result.candidate_id not in candidate_ids:
                raise ValueError("falsification result references an unknown candidate")
        selected_results = [
            result
            for result in self.falsification_results
            if result.candidate_id == self.selected_candidate_id
        ]
        if not selected_results:
            raise ValueError("selected candidate requires a falsification result")
        if any(result.verdict != "survives" for result in selected_results):
            raise ValueError(
                "selected candidate must survive every falsification check"
            )
        rejected_ids = {
            alternative.candidate.candidate_id
            for alternative in self.rejected_alternatives
        }
        if self.selected_candidate_id in rejected_ids:
            raise ValueError("selected candidate cannot also be rejected")
        known_evidence = set(self.evidence_refs)
        referenced_evidence = {
            ref for constraint in self.constraints for ref in constraint.evidence_refs
        } | {
            ref for result in self.falsification_results for ref in result.evidence_refs
        }
        if not referenced_evidence.issubset(known_evidence):
            raise ValueError("nested evidence reference is absent from evidence_refs")
        return self


class SignedDecisionPackageV1(ContractModel):
    package: DecisionPackageV1
    digest: str = Field(pattern=DIGEST_PATTERN)
    signature: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    algorithm: Literal["HMAC-SHA256"] = "HMAC-SHA256"
    key_id: str = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def digest_matches_package(self) -> "SignedDecisionPackageV1":
        if self.digest != sha256_ref(self.package):
            raise ValueError("decision package digest does not match the package")
        return self

    @classmethod
    def sign(
        cls,
        package: DecisionPackageV1,
        key: bytes,
        key_id: str,
    ) -> "SignedDecisionPackageV1":
        if len(key) < 32:
            raise ValueError("decision signing key must contain at least 32 bytes")
        signature = (
            base64.urlsafe_b64encode(
                hmac.new(key, canonical_json(package), hashlib.sha256).digest()
            )
            .rstrip(b"=")
            .decode("ascii")
        )
        return cls(
            package=package,
            digest=sha256_ref(package),
            signature=signature,
            key_id=key_id,
        )

    def verify(
        self,
        key: bytes,
        *,
        expected_key_id: Optional[str] = None,
        at: Optional[datetime] = None,
    ) -> bool:
        if len(key) < 32:
            return False
        if expected_key_id is not None and self.key_id != expected_key_id:
            return False
        current = _require_aware(at or _utc_now(), "at")
        if current < self.package.created_at or current >= self.package.expires_at:
            return False
        expected = (
            base64.urlsafe_b64encode(
                hmac.new(key, canonical_json(self.package), hashlib.sha256).digest()
            )
            .rstrip(b"=")
            .decode("ascii")
        )
        return hmac.compare_digest(self.signature, expected)


class DecisionPackageCloudEventV1(ContractModel):
    specversion: Literal["1.0"] = "1.0"
    id: str = Field(min_length=1, max_length=512)
    source: str = Field(pattern=r"^[a-z][a-z0-9+.-]*:.+$")
    type: Literal["ai.llm-d.gcl.decision-package.v1"] = (
        "ai.llm-d.gcl.decision-package.v1"
    )
    subject: str = Field(min_length=1, max_length=512)
    time: datetime
    datacontenttype: Literal["application/json"] = "application/json"
    dataschema: Literal[SCHEMA_URI] = SCHEMA_URI
    correlationid: str = Field(min_length=1, max_length=256)
    causationid: str = Field(min_length=1, max_length=256)
    idempotencyid: str = Field(min_length=1, max_length=256)
    tenant: str = Field(min_length=1, max_length=256)
    zone: str = Field(min_length=1, max_length=256)
    traceparent: Optional[str] = Field(
        default=None,
        pattern=r"^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$",
    )
    expiry: datetime
    evidence: list[str] = Field(min_length=1)
    data: SignedDecisionPackageV1

    @field_validator("time", "expiry")
    @classmethod
    def timestamps_must_be_aware(cls, value: datetime, info) -> datetime:
        return _require_aware(value, info.field_name)


def to_cloud_event(
    signed: SignedDecisionPackageV1,
    *,
    source: str,
    traceparent: Optional[str] = None,
) -> DecisionPackageCloudEventV1:
    package = signed.package
    event_fingerprint = sha256_ref(
        f"{package.package_id}:{signed.digest}:ai.llm-d.gcl.decision-package.v1"
    ).split(":", 1)[1]
    return DecisionPackageCloudEventV1(
        id=f"urn:sha256:{event_fingerprint}",
        source=source,
        subject=f"decision-package/{package.package_id}",
        time=package.created_at,
        correlationid=package.correlation_id,
        causationid=package.causation_id,
        idempotencyid=package.idempotency_id,
        tenant=package.tenant,
        zone=package.zone,
        traceparent=traceparent,
        expiry=package.expires_at,
        evidence=package.evidence_refs,
        data=signed,
    )


def build_decision_package(
    *,
    constraints: list[Constraint],
    action_plan: ActionPlan,
    trajectory: Trajectory,
    falsification: FalsificationResult,
    evidence: list[Evidence],
    correlation_id: str,
    proposer: ProposerIdentity,
    tenant: str,
    zone: str,
    ttl_seconds: int,
    signing_key: bytes,
    signing_key_id: str,
    agent_promotion_attestation: Optional[dict[str, Any]] = None,
    causation_id: Optional[str] = None,
    idempotency_id: Optional[str] = None,
) -> SignedDecisionPackageV1:
    """Translate one surviving cycle into the owned, signed decision contract."""
    created_at = _utc_now()
    expires_at = created_at + timedelta(seconds=ttl_seconds)
    evidence_by_id = {str(item.id): sha256_ref(item) for item in evidence}
    producer_evidence_refs = {
        ref
        for item in evidence
        for ref in item.metadata.get("producer_evidence_refs", [])
        if isinstance(ref, str) and re.fullmatch(DIGEST_PATTERN, ref)
    }
    evidence_refs = sorted(set(evidence_by_id.values()) | producer_evidence_refs)
    evidence_sources = sorted({item.source for item in evidence if item.source.strip()})
    if not evidence_refs:
        raise ValueError("a decision package requires at least one evidence reference")
    if not evidence_sources:
        raise ValueError("a decision package requires at least one evidence source")

    constraint_contracts = []
    for constraint in constraints:
        refs = [
            evidence_by_id[str(evidence_id)]
            for evidence_id in constraint.justification_evidence_ids
            if str(evidence_id) in evidence_by_id
        ]
        constraint_contracts.append(
            DecisionConstraint(
                constraint_id=str(constraint.id),
                constraint_type=constraint.type.value,
                hard=constraint.hard,
                bound=constraint.bound,
                confidence=constraint.confidence,
                evidence_refs=refs or evidence_refs,
            )
        )

    candidates = []
    for index, step in enumerate(action_plan.steps):
        if step.action_type not in ACTION_CLASS_NAMES:
            if index == action_plan.committed_step_index:
                raise ValueError(
                    "selected action does not map to a canonical fleet action class"
                )
            continue
        candidate_payload = {
            "step_index": step.step_index,
            "action_type": step.action_type,
            "parameters": step.parameters,
            "predicted_effect": step.predicted_effect,
        }
        candidates.append(
            DecisionCandidate(
                candidate_id=f"candidate-{sha256_ref(candidate_payload).split(':', 1)[1][:24]}",
                action_class=ACTION_CLASS_NAMES[step.action_type],
                parameters=step.parameters,
                predicted_effect=step.predicted_effect,
                confidence=trajectory.confidence,
            )
        )

    selected = candidates[0]
    rejected = [
        RejectedAlternative(
            candidate=candidate,
            reason_code="RECEDING_HORIZON_NOT_SELECTED",
            reasoning="Candidate was not selected for this receding-horizon decision.",
        )
        for candidate in candidates[1:]
    ]
    check_id = falsification.failed_check or "all-required-checks"
    decision_falsification = DecisionFalsificationResult(
        candidate_id=selected.candidate_id,
        check_id=check_id,
        verdict=falsification.verdict.value,
        reasoning=falsification.reasoning,
        evidence_refs=evidence_refs,
    )

    action_class = selected.action_class
    compatibility_attestation = None
    if agent_promotion_attestation is not None:
        raw_decision = str(
            agent_promotion_attestation.get(
                "verdict",
                agent_promotion_attestation.get("decision", "unavailable"),
            )
        ).lower()
        if raw_decision not in {"allow", "refuse", "route_human", "unavailable"}:
            raw_decision = "unavailable"
        compatibility_attestation = AgentPromotionCompatibilityAttestation(
            subject=proposer.agent_id,
            action_class=action_class,
            decision=raw_decision,
            consequence_score=float(
                agent_promotion_attestation.get("consequence_score", 0.0)
            ),
            autonomy_ceiling=float(agent_promotion_attestation.get("ceiling", 0.0)),
            attestation_ref=sha256_ref(agent_promotion_attestation),
            issued_at=created_at,
            expires_at=expires_at,
        )
    package = DecisionPackageV1(
        created_at=created_at,
        expires_at=expires_at,
        correlation_id=correlation_id,
        causation_id=causation_id or correlation_id,
        idempotency_id=idempotency_id or f"decision:{correlation_id}",
        tenant=tenant,
        zone=zone,
        proposer=proposer,
        agent_promotion=compatibility_attestation,
        constraints=constraint_contracts,
        candidates=candidates,
        selected_candidate_id=selected.candidate_id,
        rejected_alternatives=rejected,
        falsification_results=[decision_falsification],
        confidence=min(
            [trajectory.confidence]
            + [constraint.confidence for constraint in constraints]
        ),
        evidence_sources=evidence_sources,
        evidence_refs=evidence_refs,
    )
    return SignedDecisionPackageV1.sign(package, signing_key, signing_key_id)


def decision_package_schema() -> dict[str, Any]:
    return SignedDecisionPackageV1.model_json_schema()


def decision_package_cloud_event_schema() -> dict[str, Any]:
    return DecisionPackageCloudEventV1.model_json_schema()
