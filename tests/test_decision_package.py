from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from gcl.domain.contracts import (
    ActionPlan,
    ActionStep,
    Constraint,
    Evidence,
    FalsificationResult,
    Trajectory,
    TrajectoryPoint,
)
from gcl.domain.decision_package import (
    DecisionPackageV1,
    DecisionCandidate,
    ProposerIdentity,
    SignedDecisionPackageV1,
    build_decision_package,
    canonical_json,
    decision_package_cloud_event_schema,
    decision_package_schema,
    sha256_ref,
    to_cloud_event,
)
from gcl.domain.enums import ConstraintSource, ConstraintType, Verdict


KEY = b"a-secure-test-key-with-at-least-thirty-two-bytes"


def _signed_package(
    agent_promotion_attestation: dict | None = None,
) -> SignedDecisionPackageV1:
    evidence = Evidence(
        metric="latency_ms",
        value=6200,
        timestamp=datetime(2026, 7, 13, tzinfo=timezone.utc),
        source="deepfield-fleet",
        metadata={"producer_evidence_refs": ["sha256:" + "f" * 64]},
    )
    constraint = Constraint(
        type=ConstraintType.LATENCY,
        bound=5000,
        hard=True,
        justification_evidence_ids=[evidence.id],
        confidence=0.91,
        source=ConstraintSource.DETERMINISTIC,
    )
    plan = ActionPlan(
        steps=[
            ActionStep(
                step_index=0,
                action_type="scale",
                parameters={"pool": "primary", "replicas": 6},
                predicted_effect={"latency_ms": 3900},
            ),
            ActionStep(
                step_index=1,
                action_type="shed_load",
                parameters={"max_inflight": 100},
            ),
        ],
        committed_step_index=0,
        horizon_steps=2,
    )
    trajectory = Trajectory(
        points=[TrajectoryPoint(step=0, value=6200)],
        horizon_steps=1,
        confidence=0.87,
        generated_at=datetime(2026, 7, 13, tzinfo=timezone.utc),
    )
    falsification = FalsificationResult(
        action_id=uuid4(),
        verdict=Verdict.SURVIVES,
        reasoning="All deterministic disconfirmation checks survived.",
        evidence_ids=[evidence.id],
    )
    return build_decision_package(
        constraints=[constraint],
        action_plan=plan,
        trajectory=trajectory,
        falsification=falsification,
        evidence=[evidence],
        correlation_id="corr-123",
        proposer=ProposerIdentity(
            agent_id="gcl",
            workload_identity="spiffe://llm-d.ai/ns/gcl/sa/controller",
            trust_domain="llm-d.ai",
        ),
        tenant="tenant-a",
        zone="us-central",
        ttl_seconds=300,
        signing_key=KEY,
        signing_key_id="test-key-v1",
        agent_promotion_attestation=agent_promotion_attestation,
    )


class TestDecisionPackageV1:
    def test_contains_required_governance_material(self):
        signed = _signed_package()
        package = signed.package

        assert package.schema_version.endswith("decision-package/v1")
        assert package.constraints
        assert len(package.candidates) == 2
        assert len(package.rejected_alternatives) == 1
        assert package.falsification_results[0].verdict == "survives"
        assert package.confidence == 0.87
        assert package.evidence_sources == ["deepfield-fleet"]
        assert all(ref.startswith("sha256:") for ref in package.evidence_refs)
        assert "sha256:" + "f" * 64 in package.evidence_refs
        assert package.correlation_id == "corr-123"
        assert package.idempotency_id == "decision:corr-123"
        assert package.agent_promotion is None
        assert package.proposer.workload_identity.startswith("spiffe://")

    def test_optional_agent_promotion_attestation_is_non_authoritative(self):
        package = _signed_package(
            {
                "verdict": "refuse",
                "consequence_score": 0.7,
                "ceiling": 0.5,
            }
        ).package

        assert package.agent_promotion is not None
        assert package.agent_promotion.decision == "refuse"
        assert package.agent_promotion.non_authoritative is True

    def test_canonical_signing_and_verification_are_deterministic(self):
        signed = _signed_package()
        signed_again = SignedDecisionPackageV1.sign(
            signed.package,
            KEY,
            "test-key-v1",
        )
        assert canonical_json(signed.package) == canonical_json(signed_again.package)
        assert signed.digest == sha256_ref(signed.package)
        assert signed.signature == signed_again.signature
        assert signed.verify(
            KEY,
            expected_key_id="test-key-v1",
            at=signed.package.created_at + timedelta(seconds=1),
        )

    def test_expired_package_does_not_verify(self):
        signed = _signed_package()
        assert not signed.verify(KEY, at=signed.package.expires_at)

    def test_tampering_is_rejected_before_signature_verification(self):
        signed = _signed_package()
        payload = signed.model_dump(mode="json")
        payload["package"]["tenant"] = "different-tenant"
        with pytest.raises(ValidationError, match="digest does not match"):
            SignedDecisionPackageV1.model_validate(payload)

    def test_unknown_fields_are_rejected(self):
        signed = _signed_package()
        payload = signed.package.model_dump(mode="json")
        payload["unexpected"] = True
        with pytest.raises(ValidationError, match="Extra inputs"):
            DecisionPackageV1.model_validate(payload)

    def test_naive_expiry_is_rejected(self):
        signed = _signed_package()
        payload = signed.package.model_dump(mode="python")
        payload["expires_at"] = datetime.now()
        with pytest.raises(ValidationError, match="timezone"):
            DecisionPackageV1.model_validate(payload)

    def test_noncanonical_fleet_action_class_is_rejected(self):
        with pytest.raises(ValidationError):
            DecisionCandidate(
                candidate_id="candidate-alert",
                action_class="fleet.alert",
                parameters={},
                confidence=0.9,
            )

    def test_selected_candidate_must_survive_falsification(self):
        payload = _signed_package().package.model_dump(mode="json")
        payload["falsification_results"][0]["verdict"] = "fails"
        with pytest.raises(ValidationError, match="must survive"):
            DecisionPackageV1.model_validate(payload)

    def test_selected_candidate_requires_falsification_evidence(self):
        payload = _signed_package().package.model_dump(mode="json")
        payload["falsification_results"][0]["candidate_id"] = payload["candidates"][1][
            "candidate_id"
        ]
        with pytest.raises(ValidationError, match="requires a falsification result"):
            DecisionPackageV1.model_validate(payload)


class TestDecisionPackageCloudEvent:
    def test_structured_event_is_cloudevents_1_0_and_deterministic(self):
        signed = _signed_package()
        event_one = to_cloud_event(
            signed,
            source="spiffe://llm-d.ai/ns/gcl/sa/controller",
        )
        event_two = to_cloud_event(
            signed,
            source="spiffe://llm-d.ai/ns/gcl/sa/controller",
        )

        assert event_one.specversion == "1.0"
        assert event_one.id == event_two.id
        assert event_one.data.digest == signed.digest
        assert event_one.correlationid == signed.package.correlation_id
        assert event_one.idempotencyid == signed.package.idempotency_id
        assert event_one.expiry == signed.package.expires_at

    def test_json_schema_exports_are_versioned(self):
        package_schema = decision_package_schema()
        event_schema = decision_package_cloud_event_schema()
        assert package_schema["title"] == "SignedDecisionPackageV1"
        assert event_schema["title"] == "DecisionPackageCloudEventV1"
        assert event_schema["properties"]["specversion"]["const"] == "1.0"
