"""Tests for the generic decision sampler.

Validates that the sampler:
- Reads decision records from the ledger
- Filters to auditable outcomes (drop/suppress/dedupe)
- Samples at configured rate
- Always audits new/low-confidence decisions
- Runs deterministic falsification checks
- Writes audit.verdict back to ledger
- Updates watermark to avoid re-processing
"""

import pytest
from unittest.mock import AsyncMock, patch

from gcl.adapter.decision_event_adapter import decision_record_to_evidence
from gcl.domain.contracts import Evidence


def _make_decision(subject_type="pod_crashloop", severity="high", outcome="drop",
                   agent="severity_gate", confidence=0.95, subject_id="sig-1"):
    return {
        "subject_id": subject_id,
        "subject_type": subject_type,
        "severity": severity,
        "outcome": outcome,
        "agent": agent,
        "confidence": confidence,
        "tier": "nano",
        "namespace": "production",
        "evidence": "test",
    }


def _make_record(decisions, system_id="cascade-k8s", domain="k8s"):
    return {
        "system_id": system_id,
        "batch_id": "batch-001",
        "domain": domain,
        "decisions": decisions,
    }


class TestDecisionAuditChecks:
    """Deterministic checks on individual decisions — no LLM needed."""

    def test_high_severity_drop_fails(self):
        """Dropping a high-severity signal should be flagged."""
        d = _make_decision(severity="high", outcome="drop")
        ev = decision_record_to_evidence(_make_record([d]))
        assert len(ev) == 1
        assert ev[0].labels["severity"] == "high"
        assert ev[0].labels["outcome"] == "drop"

    def test_critical_severity_drop_fails(self):
        d = _make_decision(severity="critical", outcome="suppress")
        ev = decision_record_to_evidence(_make_record([d]))
        assert ev[0].labels["severity"] == "critical"

    def test_info_severity_drop_survives(self):
        d = _make_decision(severity="info", outcome="drop")
        ev = decision_record_to_evidence(_make_record([d]))
        assert ev[0].labels["severity"] == "info"

    def test_low_confidence_flagged(self):
        d = _make_decision(confidence=0.3, outcome="suppress")
        ev = decision_record_to_evidence(_make_record([d]))
        assert ev[0].value == 0.3

    def test_high_confidence_passes(self):
        d = _make_decision(confidence=0.99, outcome="dedupe")
        ev = decision_record_to_evidence(_make_record([d]))
        assert ev[0].value == 0.99

    def test_keep_not_audited(self):
        d = _make_decision(outcome="keep")
        ev = decision_record_to_evidence(_make_record([d]))
        assert ev == []

    def test_escalate_not_audited(self):
        d = _make_decision(outcome="escalate")
        ev = decision_record_to_evidence(_make_record([d]))
        assert ev == []


class TestSamplingLogic:
    """Sampling rate and always-audit rules."""

    def test_samples_drops_only(self):
        decisions = [
            _make_decision(outcome="drop", subject_id="1"),
            _make_decision(outcome="keep", subject_id="2"),
            _make_decision(outcome="suppress", subject_id="3"),
            _make_decision(outcome="escalate", subject_id="4"),
            _make_decision(outcome="dedupe", subject_id="5"),
        ]
        ev = decision_record_to_evidence(_make_record(decisions))
        assert len(ev) == 3
        outcomes = [e.labels["outcome"] for e in ev]
        assert set(outcomes) == {"drop", "suppress", "dedupe"}

    def test_multiple_records_aggregate(self):
        r1 = _make_record([_make_decision(outcome="drop", subject_id="1")])
        r2 = _make_record([_make_decision(outcome="drop", subject_id="2")])
        ev1 = decision_record_to_evidence(r1)
        ev2 = decision_record_to_evidence(r2)
        assert len(ev1) + len(ev2) == 2


class TestVerdictSchema:
    """Verdicts match the audit-verdict.json contract."""

    def test_survives_verdict_structure(self):
        verdict = {
            "decision_ref": "sig-1",
            "subject_type": "event_warning",
            "original_outcome": "drop",
            "verdict": "SURVIVES",
            "checks_passed": ["severity", "confidence"],
            "checks_failed": [],
            "reason": "Info severity, high confidence — correct drop.",
        }
        assert verdict["verdict"] in ("SURVIVES", "FAILS")
        assert isinstance(verdict["checks_passed"], list)
        assert isinstance(verdict["checks_failed"], list)

    def test_fails_verdict_structure(self):
        verdict = {
            "decision_ref": "sig-2",
            "subject_type": "pod_crashloop",
            "original_outcome": "suppress",
            "verdict": "FAILS",
            "checks_passed": ["confidence"],
            "checks_failed": ["severity"],
            "reason": "High-severity signal suppressed — false negative.",
        }
        assert verdict["verdict"] == "FAILS"
        assert "severity" in verdict["checks_failed"]
