"""The cascade reader fails a dangerous judgment-call drop and survives a dedupe.

Live finding on infra01 (2026-10-23): the verified_repeat_update profile
made medium the designed dedup band (identity admission requires medium),
so a severity check that fails medium dedupes produced 100% FAILS verdicts
on every dedupe decision — pure policy noise that drowned real signals.
The corrected policy (matching gcl.loop.decision_sampler.audit_decision):
dedupe is deterministic content-hash matching — the first occurrence is
always delivered, so folding repeats is correct regardless of severity.
Only judgment-call drops (suppress/drop) are flagged, at high severity or
above. Confidence below 0.8 fails for every outcome.
"""

from gcl.loop.cascade_audit import judge_drop


def test_medium_dedupe_survives():
    """The live bug case: medium dedupe at full confidence must survive.

    On infra01 every one of these was failed with 'medium dedupe failed
    severity' while the engine was working exactly as designed.
    """
    verdict = judge_drop(
        {
            "subject_id": "case-dedupe",
            "subject_type": "event_claimmisbound",
            "severity": "medium",
            "outcome": "dedupe",
            "agent": "deduplicate",
            "confidence": 1.0,
        },
        domain="k8s",
    )
    assert verdict["verdict"] == "SURVIVES"
    assert "severity" in verdict["checks_passed"]
    assert verdict["checks_failed"] == []


def test_critical_dedupe_survives_severity_check():
    """Dedupe is exempt from severity at ANY level: the first occurrence
    of the content was delivered, so folding a repeat cannot lose a signal."""
    verdict = judge_drop(
        {
            "subject_id": "case-critical-dedupe",
            "subject_type": "event_backoff",
            "severity": "critical",
            "outcome": "dedupe",
            "agent": "deduplicate",
            "confidence": 1.0,
        },
        domain="k8s",
    )
    assert "severity" in verdict["checks_passed"]
    # Verdict may still FAIL on other checks, but never on severity.


def test_high_suppress_fails_severity():
    """A judgment-call suppression at high severity is a genuine violation:
    the engine's fail-open gate should have prevented it."""
    verdict = judge_drop(
        {
            "subject_id": "case-high-suppress",
            "subject_type": "pod_failed",
            "severity": "high",
            "outcome": "suppress",
            "agent": "suppress_pod_failed_repeat",
            "confidence": 1.0,
        },
        domain="k8s",
    )
    assert verdict["verdict"] == "FAILS"
    assert "severity" in verdict["checks_failed"]


def test_medium_suppress_low_confidence_fails():
    """Medium suppressions by qualified agents are designed behavior, so
    severity passes; this one fails on confidence alone."""
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
    assert "confidence" in verdict["checks_failed"]
    assert "severity" not in verdict["checks_failed"]


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
    assert "page_size=10000" in url, (
        "audit must request its full intended page size — the gateway "
        "will honor page_size once fixed, and a 100-entry sample would "
        "silently starve the audit"
    )
    from_ts = int(url.split("from_ts=")[1].split("&")[0])
    assert before - 30 * 60 * 1000 <= from_ts <= after - 30 * 60 * 1000 + 2000
