"""Read cascade decision receipts and post an audit verdict for each drop.

This process speaks only HTTP. A drop at medium severity or above fails.
An info drop at confidence 0.8 or higher survives.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.parse
import urllib.request

_DROP_OUTCOMES = {"drop", "suppress", "dedupe"}
_DANGEROUS = {"medium", "high", "critical"}


def judge_drop(decision: dict, *, domain: str) -> dict:
    checks_passed: list[str] = []
    checks_failed: list[str] = []
    severity = str(decision.get("severity", ""))
    confidence = float(decision.get("confidence", 0))
    if severity in _DANGEROUS:
        checks_failed.append("severity")
    else:
        checks_passed.append("severity")
    if confidence < 0.8:
        checks_failed.append("confidence")
    else:
        checks_passed.append("confidence")
    verdict = "FAILS" if checks_failed else "SURVIVES"
    failed = ", ".join(checks_failed)
    reason = (
        f"{severity} {decision.get('outcome', '')} failed {failed}"
        if checks_failed
        else f"{severity} {decision.get('outcome', '')} passed the audit checks"
    )
    return {
        "decision_ref": decision.get("subject_id", ""),
        "subject_type": decision.get("subject_type", ""),
        "original_outcome": decision.get("outcome", ""),
        "original_agent": decision.get("agent", ""),
        "original_confidence": confidence,
        "severity": severity,
        "domain": domain,
        "verdict": verdict,
        "checks_passed": checks_passed,
        "checks_failed": checks_failed,
        "probe_result": None,
        "reason": reason,
    }


def audit(ledger_url: str, token: str) -> int:
    entries = _get(ledger_url, token, "decision.record")
    written = 0
    for entry in entries:
        record = json.loads(entry["content"]) if isinstance(entry["content"], str) else entry["content"]
        for decision in record.get("decisions", []):
            if decision.get("outcome") not in _DROP_OUTCOMES:
                continue
            verdict = judge_drop(decision, domain=str(record.get("domain", "")))
            _post_verdict(ledger_url, token, verdict, str(entry.get("correlation_id", "")))
            written += 1
    return written


def _get(ledger_url: str, token: str, entry_type: str) -> list[dict]:
    query = urllib.parse.urlencode({"entry_type": entry_type})
    request = urllib.request.Request(
        f"{ledger_url.rstrip('/')}/api/entries?{query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.load(response)
    if isinstance(payload, list):
        return payload
    return list(payload.get("entries", []))


def _post_verdict(ledger_url: str, token: str, verdict: dict, correlation_id: str) -> None:
    content = json.dumps(verdict, sort_keys=True, separators=(",", ":"))
    key_material = f"audit.verdict\0{correlation_id}\0{verdict['decision_ref']}"
    entry = {
        "entry_type": "audit.verdict",
        "agent_id": "governed-cognitive-loop",
        "content": content,
        "content_type": "application/json",
        "source_id": "gcl-cascade-audit",
        "correlation_id": correlation_id,
        "idempotency_key": hashlib.sha256(key_material.encode()).hexdigest(),
        "input_hash": hashlib.sha256(content.encode()).hexdigest(),
    }
    raw = json.dumps(entry).encode()
    request = urllib.request.Request(
        f"{ledger_url.rstrip('/')}/api/receipts",
        data=raw,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger-url", required=True)
    parser.add_argument("--token", required=True)
    args = parser.parse_args(argv)
    written = audit(args.ledger_url, args.token)
    print(written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
