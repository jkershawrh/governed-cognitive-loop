"""Tests for the generic decision event adapter.

Validates that decision records are correctly converted to GCL Evidence
for falsification. Tests use the decision-record.json schema contract.
"""

import pytest

from gcl.adapter.decision_event_adapter import (
    decision_to_evidence,
    decision_record_to_evidence,
)


class TestDecisionToEvidence:
    def test_converts_drop_decision(self):
        decision = {
            "subject_id": "sig-123",
            "subject_type": "pod_crashloop",
            "severity": "high",
            "outcome": "drop",
            "agent": "severity_gate",
            "confidence": 0.95,
            "tier": "nano",
            "namespace": "production",
            "evidence": "severity below threshold",
        }
        ev = decision_to_evidence(decision, "cascade-k8s")
        assert ev.metric == "decision.outcome"
        assert ev.value == 0.95
        assert ev.source == "cascade-k8s"
        assert ev.labels["subject_type"] == "pod_crashloop"
        assert ev.labels["severity"] == "high"
        assert ev.labels["outcome"] == "drop"
        assert ev.labels["agent"] == "severity_gate"
        assert ev.metadata["subject_id"] == "sig-123"

    def test_handles_missing_fields(self):
        decision = {"outcome": "keep", "confidence": 0.5}
        ev = decision_to_evidence(decision)
        assert ev.source == "unknown"
        assert ev.labels["subject_type"] == ""
        assert ev.labels["severity"] == ""

    def test_confidence_maps_to_value(self):
        ev = decision_to_evidence({"confidence": 0.72, "outcome": "suppress"})
        assert ev.value == 0.72


class TestDecisionRecordToEvidence:
    def test_filters_auditable_outcomes(self):
        record = {
            "system_id": "cascade-aap",
            "domain": "aap",
            "decisions": [
                {"subject_id": "1", "outcome": "drop", "confidence": 0.9, "subject_type": "a", "severity": "info", "agent": "x"},
                {"subject_id": "2", "outcome": "keep", "confidence": 0.8, "subject_type": "b", "severity": "high", "agent": "y"},
                {"subject_id": "3", "outcome": "suppress", "confidence": 0.95, "subject_type": "c", "severity": "low", "agent": "z"},
                {"subject_id": "4", "outcome": "dedupe", "confidence": 1.0, "subject_type": "d", "severity": "info", "agent": "w"},
                {"subject_id": "5", "outcome": "escalate", "confidence": 0.7, "subject_type": "e", "severity": "critical", "agent": "v"},
            ],
        }
        evidence = decision_record_to_evidence(record)
        assert len(evidence) == 3
        outcomes = [e.labels["outcome"] for e in evidence]
        assert "keep" not in outcomes
        assert "escalate" not in outcomes
        assert "drop" in outcomes
        assert "suppress" in outcomes
        assert "dedupe" in outcomes

    def test_empty_record(self):
        evidence = decision_record_to_evidence({"system_id": "test", "decisions": []})
        assert evidence == []

    def test_all_keeps_produces_no_evidence(self):
        record = {
            "system_id": "test",
            "decisions": [
                {"subject_id": "1", "outcome": "keep", "confidence": 1.0, "subject_type": "a", "severity": "info", "agent": "x"},
                {"subject_id": "2", "outcome": "escalate", "confidence": 0.9, "subject_type": "b", "severity": "high", "agent": "y"},
            ],
        }
        evidence = decision_record_to_evidence(record)
        assert evidence == []

    def test_system_id_propagates(self):
        record = {
            "system_id": "my-custom-system",
            "decisions": [{"subject_id": "1", "outcome": "drop", "confidence": 0.8, "subject_type": "a", "severity": "info", "agent": "x"}],
        }
        evidence = decision_record_to_evidence(record)
        assert evidence[0].source == "my-custom-system"

    def test_domain_agnostic(self):
        """Adapter works with any system_id — not cascade-specific."""
        for system in ["cascade-k8s", "deepfield-fleet", "fraud-detector", "custom-pipeline"]:
            record = {
                "system_id": system,
                "decisions": [{"subject_id": "1", "outcome": "suppress", "confidence": 0.9, "subject_type": "signal", "severity": "info", "agent": "agent"}],
            }
            evidence = decision_record_to_evidence(record)
            assert evidence[0].source == system
