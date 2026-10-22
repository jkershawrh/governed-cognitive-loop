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


def test_audit_windows_decision_query(monkeypatch):
    """The audit must read a bounded window, not full history.

    Found live on infra01: the ledger holds 13M+ decision.records; an
    unwindowed query pulls the gateway's full-content cap (~10k entries,
    >15s) and the 15s timeout kills the audit before it judges anything.
    The query must carry from_ts (Unix ms) for the recent window only.
    """
    import time
    from unittest.mock import MagicMock, patch

    from gcl.loop import cascade_audit

    before = int(time.time() * 1000)

    response = MagicMock()
    response.read.return_value = b'{"entries": []}'
    response.__enter__.return_value = response
    opener = MagicMock(return_value=response)

    with patch.object(cascade_audit.urllib.request, "urlopen", opener):
        cascade_audit.audit(
            "http://ledger.example", "t", window_minutes=30,
        )

    url = opener.call_args[0][0].full_url
    after = int(time.time() * 1000)
    assert "from_ts=" in url, "audit must window its decision query"
    from_ts = int(url.split("from_ts=")[1].split("&")[0])
    assert before - 30 * 60 * 1000 <= from_ts <= after - 30 * 60 * 1000 + 2000
