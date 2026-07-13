"""Consumer adapter for DeepField Fleet-owned CloudEvents v1.

DeepField owns the payload schemas. GCL pins their event and schema identities,
validates the shared CloudEvents envelope, and converts advisory payloads into
internal Evidence without treating any recommendation as an executable intent.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from gcl.domain.contracts import Evidence


DEEPFIELD_EVENT_SCHEMAS = {
    "io.srex.deepfield.observation.v1": "urn:srex:deepfield:schema:observation:v1",
    "io.srex.deepfield.finding.v1": "urn:srex:deepfield:schema:finding:v1",
    "io.srex.deepfield.forecast.v1": "urn:srex:deepfield:schema:forecast:v1",
    "io.srex.deepfield.remediation.proposal.v1": (
        "urn:srex:deepfield:schema:remediation-proposal:v1"
    ),
}
DEEPFIELD_SOURCE = "deepfield-fleet"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_TRACEPARENT_PATTERN = r"^[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$"


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("DeepField payload timestamps must include a timezone")
    return value.astimezone(timezone.utc)


def _require_uri(value: str) -> str:
    if ":" not in value or value.startswith(":"):
        raise ValueError("DeepField evidence URI must be absolute")
    return value


class _DeepFieldContractModel(BaseModel):
    """Pinned, strict consumer view of producer-owned v1 payloads."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class _EvidenceRefV1(_DeepFieldContractModel):
    uri: str = Field(min_length=1)
    sha256: str = Field(pattern=_SHA256_PATTERN)
    media_type: str = "application/json"

    _uri_is_absolute = field_validator("uri")(_require_uri)


class _ResourceRefV1(_DeepFieldContractModel):
    cluster: str = Field(min_length=1)
    namespace: str | None = None
    kind: str = Field(min_length=1)
    name: str = Field(min_length=1)
    uid: str | None = None


_SeverityV1 = Literal["info", "low", "medium", "high", "critical"]
_ActionClassV1 = Literal[
    "fleet.deploy",
    "fleet.scale",
    "fleet.route",
    "fleet.prewarm",
    "fleet.shed_load",
    "fleet.migrate",
    "fleet.kv_transfer",
]


class _ObservationV1(_DeepFieldContractModel):
    observation_id: str = Field(min_length=1)
    observed_at: datetime
    resource: _ResourceRefV1
    signal_type: str = Field(min_length=1)
    severity: _SeverityV1
    value: JsonValue | None = None
    unit: str | None = None
    attributes: dict[str, JsonValue] = Field(default_factory=dict)
    evidence: list[_EvidenceRefV1] = Field(min_length=1)

    _observed_at_is_aware = field_validator("observed_at")(_require_aware)


class _FindingV1(_DeepFieldContractModel):
    finding_id: str = Field(min_length=1)
    created_at: datetime
    finding_type: str = Field(min_length=1)
    severity: _SeverityV1
    summary: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    resources: list[_ResourceRefV1] = Field(min_length=1)
    observation_ids: list[str] = Field(min_length=1)
    attributes: dict[str, JsonValue] = Field(default_factory=dict)
    evidence: list[_EvidenceRefV1] = Field(min_length=1)

    _created_at_is_aware = field_validator("created_at")(_require_aware)


class _ForecastV1(_DeepFieldContractModel):
    forecast_id: str = Field(min_length=1)
    generated_at: datetime
    valid_until: datetime
    horizon_seconds: int = Field(gt=0)
    forecast_type: str = Field(min_length=1)
    target: _ResourceRefV1
    predicted_value: JsonValue
    unit: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_actions: list[_ActionClassV1] = Field(default_factory=list)
    advisory_only: Literal[True] = True
    model_version: str = Field(min_length=1)
    input_digest: str = Field(pattern=_SHA256_PATTERN)
    rejected_alternatives: list[str] = Field(default_factory=list)
    evidence: list[_EvidenceRefV1] = Field(min_length=1)

    _times_are_aware = field_validator("generated_at", "valid_until")(_require_aware)

    @model_validator(mode="after")
    def valid_window(self) -> "_ForecastV1":
        if self.valid_until <= self.generated_at:
            raise ValueError("DeepField forecast valid_until must follow generated_at")
        return self


class _RemediationProposalV1(_DeepFieldContractModel):
    proposal_id: str = Field(min_length=1)
    requested_at: datetime
    target: _ResourceRefV1
    action_class: _ActionClassV1
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    reason: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    request_digest: str = Field(pattern=_SHA256_PATTERN)
    confidence: float = Field(ge=0.0, le=1.0)
    advisory_only: Literal[True] = True
    evidence: list[_EvidenceRefV1] = Field(min_length=1)

    _requested_at_is_aware = field_validator("requested_at")(_require_aware)


_DEEPFIELD_DATA_MODELS: dict[str, type[_DeepFieldContractModel]] = {
    "io.srex.deepfield.observation.v1": _ObservationV1,
    "io.srex.deepfield.finding.v1": _FindingV1,
    "io.srex.deepfield.forecast.v1": _ForecastV1,
    "io.srex.deepfield.remediation.proposal.v1": _RemediationProposalV1,
}


class DeepFieldCloudEventV1(BaseModel):
    """Pinned consumer view of the DeepField-owned event envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    specversion: Literal["1.0"] = "1.0"
    id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    type: Literal[
        "io.srex.deepfield.observation.v1",
        "io.srex.deepfield.finding.v1",
        "io.srex.deepfield.forecast.v1",
        "io.srex.deepfield.remediation.proposal.v1",
    ]
    subject: str = Field(min_length=1)
    time: datetime
    datacontenttype: Literal["application/json"] = "application/json"
    dataschema: str
    correlationid: str = Field(min_length=1)
    causationid: str = Field(min_length=1)
    idempotencykey: str = Field(min_length=1)
    tenant: str = Field(min_length=1)
    zone: str = Field(min_length=1)
    traceparent: str = Field(pattern=_TRACEPARENT_PATTERN)
    expiresat: datetime
    data: dict[str, Any]

    @model_validator(mode="before")
    @classmethod
    def payload_matches_pinned_producer_contract(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        event_type = value.get("type")
        payload_model = _DEEPFIELD_DATA_MODELS.get(event_type)
        if payload_model is None:
            return value
        validated = payload_model.model_validate(value.get("data"))
        projected = dict(value)
        projected["data"] = validated.model_dump(mode="python")
        return projected

    @field_validator("time", "expiresat")
    @classmethod
    def timestamps_are_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("DeepField event timestamps must include a timezone")
        return value.astimezone(timezone.utc)

    @field_validator("source", "dataschema")
    @classmethod
    def identifiers_are_absolute(cls, value: str) -> str:
        if ":" not in value or value.startswith(":"):
            raise ValueError(
                "DeepField event identifiers must be absolute URIs or URNs"
            )
        return value

    @model_validator(mode="after")
    def contract_identity_and_expiry_match(self) -> "DeepFieldCloudEventV1":
        if self.dataschema != DEEPFIELD_EVENT_SCHEMAS[self.type]:
            raise ValueError("DeepField event type and dataschema do not match")
        if self.expiresat <= self.time:
            raise ValueError("DeepField event expiry must follow event time")
        payload_timestamp = {
            "io.srex.deepfield.observation.v1": "observed_at",
            "io.srex.deepfield.finding.v1": "created_at",
            "io.srex.deepfield.forecast.v1": "generated_at",
            "io.srex.deepfield.remediation.proposal.v1": "requested_at",
        }[self.type]
        if self.data[payload_timestamp] != self.time:
            raise ValueError("DeepField event time must match its payload timestamp")
        if (
            self.type == "io.srex.deepfield.forecast.v1"
            and self.data["valid_until"] != self.expiresat
        ):
            raise ValueError(
                "DeepField forecast event expiry must match payload valid_until"
            )
        evidence = self.data.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("DeepField event data requires evidence references")
        for ref in evidence:
            if not isinstance(ref, dict) or not isinstance(ref.get("sha256"), str):
                raise ValueError("DeepField evidence references require sha256")
            if not re.fullmatch(_SHA256_PATTERN, ref["sha256"]):
                raise ValueError("DeepField evidence sha256 must be 64 lowercase hex")
        return self

    def is_expired(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        return current >= self.expiresat


def _numeric(value: Any, fallback: float) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return fallback


def _resource_labels(data: dict[str, Any], key: str) -> dict[str, str]:
    resource = data.get(key, {})
    if not isinstance(resource, dict):
        return {}
    return {
        field: str(resource[field])
        for field in ("cluster", "namespace", "kind", "name", "uid")
        if resource.get(field) is not None
    }


def deepfield_event_to_evidence(event: DeepFieldCloudEventV1) -> list[Evidence]:
    """Convert one DeepField advisory event to GCL Evidence."""
    data = event.data
    producer_refs = [
        f"sha256:{item['sha256']}"
        for item in data["evidence"]
        if isinstance(item, dict)
    ]
    base_metadata = {
        "producer_event_id": event.id,
        "producer_event_type": event.type,
        "producer_dataschema": event.dataschema,
        "producer_source": event.source,
        "producer_evidence_refs": producer_refs,
        "producer_causation_id": event.causationid,
        "producer_idempotency_key": event.idempotencykey,
    }
    base_labels = {
        "producer": DEEPFIELD_SOURCE,
        "tenant": event.tenant,
        "zone": event.zone,
        "subject": event.subject,
    }

    if event.type == "io.srex.deepfield.observation.v1":
        metric = str(data.get("signal_type", "deepfield_observation"))
        value = _numeric(data.get("value"), 0.0)
        labels = {**base_labels, **_resource_labels(data, "resource")}
    elif event.type == "io.srex.deepfield.finding.v1":
        metric = str(data.get("finding_type", "deepfield_finding"))
        value = _numeric(data.get("confidence"), 0.0)
        resources = data.get("resources", [])
        resource = resources[0] if isinstance(resources, list) and resources else {}
        labels = {
            **base_labels,
            **(
                {
                    key: str(resource[key])
                    for key in ("cluster", "namespace", "kind", "name", "uid")
                    if isinstance(resource, dict) and resource.get(key) is not None
                }
            ),
        }
    elif event.type == "io.srex.deepfield.forecast.v1":
        metric = str(data.get("forecast_type", "deepfield_forecast"))
        value = _numeric(
            data.get("predicted_value"), _numeric(data.get("confidence"), 0.0)
        )
        labels = {**base_labels, **_resource_labels(data, "target")}
    else:
        action_class = str(data.get("action_class", "unknown"))
        metric = f"deepfield_remediation_{action_class.replace('.', '_')}"
        value = _numeric(data.get("confidence"), 0.0)
        labels = {**base_labels, **_resource_labels(data, "target")}

    return [
        Evidence(
            metric=metric,
            value=value,
            timestamp=event.time,
            source=DEEPFIELD_SOURCE,
            labels=labels,
            metadata={**base_metadata, "producer_data": data},
        )
    ]
