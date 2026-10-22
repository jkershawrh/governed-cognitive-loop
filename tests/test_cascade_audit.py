"""The cascade reader fails a dangerous drop and survives an info drop."""

from gcl.loop.cascade_audit import judge_drop


def test_medium_suppress_fails():
    verdict = judge_drop(
        {
            "subject_id": "case-1",
            "subject_type": "event_unhealthy",
            "severity": "medium",
            "outcome": "suppress",
            "agent": "semantic_classifier",
            "confidence": 0.14,
        },
        domain="department-a",
    )
    assert verdict["verdict"] == "FAILS"
    assert "severity" in verdict["checks_failed"]


def test_info_drop_survives():
    verdict = judge_drop(
        {
            "subject_id": "info-1",
            "subject_type": "status",
            "severity": "info",
            "outcome": "drop",
            "agent": "severity_gate",
            "confidence": 1.0,
        },
        domain="department-a",
    )
    assert verdict["verdict"] == "SURVIVES"
    assert verdict["checks_failed"] == []
