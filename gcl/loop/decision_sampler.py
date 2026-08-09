"""Generic decision sampler — polls ledger for decision records and audits them.

Domain-agnostic. Does not know what system produced the decisions.
Uses the existing falsification gate pattern: deterministic checks first,
then optionally an LLM adversary probe.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
from typing import Any, Dict, List, Optional

import httpx

from gcl.adapter.decision_event_adapter import decision_record_to_evidence
from gcl.config import get_settings
from gcl.inference.client import infer, is_inference_available
from gcl.loop.ledger import LedgerClient

logger = logging.getLogger(__name__)

SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def audit_decision(decision: Dict[str, Any]) -> Dict[str, Any]:
    """Run deterministic falsification checks on a single decision.

    Returns an audit verdict matching contracts/schemas/audit-verdict.json.
    """
    checks_passed = []
    checks_failed = []

    severity = decision.get("severity", "info")
    confidence = decision.get("confidence", 1.0)
    outcome = decision.get("outcome", "keep")

    if outcome not in ("drop", "suppress", "dedupe"):
        return {
            "decision_ref": decision.get("subject_id", ""),
            "subject_type": decision.get("subject_type", ""),
            "original_outcome": outcome,
            "verdict": "SURVIVES",
            "checks_passed": ["not_auditable"],
            "checks_failed": [],
            "reason": "Only drop/suppress/dedupe decisions are audited.",
        }

    if SEVERITY_RANK.get(severity, 0) >= SEVERITY_RANK["medium"]:
        checks_failed.append("severity")
    else:
        checks_passed.append("severity")

    if confidence < 0.8:
        checks_failed.append("confidence")
    else:
        checks_passed.append("confidence")

    verdict = "FAILS" if checks_failed else "SURVIVES"
    reason = (
        f"{'|'.join(checks_failed)} check(s) failed — {severity} severity "
        f"signal {outcome}ed with {confidence:.0%} confidence."
        if checks_failed
        else f"Low severity ({severity}), high confidence ({confidence:.0%}) — correct {outcome}."
    )

    return {
        "decision_ref": decision.get("subject_id", ""),
        "subject_type": decision.get("subject_type", ""),
        "original_outcome": outcome,
        "original_agent": decision.get("agent", ""),
        "original_confidence": confidence,
        "severity": severity,
        "domain": decision.get("domain", ""),
        "verdict": verdict,
        "checks_passed": checks_passed,
        "checks_failed": checks_failed,
        "probe_result": None,
        "reason": reason,
    }


_PROBE_SYSTEM = (
    "You audit cascade compression decisions. A signal was DROPPED by an automated agent. "
    "Deterministic checks flagged this drop as suspicious (medium+ severity or low confidence). "
    "Your job: was the DROP actually correct despite the flag? "
    "Respond with JSON only: "
    '{"correct_drop": true, "reason": "..."} if the drop was justified, or '
    '{"correct_drop": false, "reason": "..."} if the signal should NOT have been dropped.'
)


async def _llm_probe_decision(decision: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not is_inference_available():
        return None
    prompt = (
        f"Signal type: {decision.get('subject_type', 'unknown')}\n"
        f"Severity: {decision.get('severity', 'unknown')}\n"
        f"Confidence: {decision.get('confidence', 'unknown')}\n"
        f"Outcome: {decision.get('outcome', 'unknown')}\n"
        f"Agent: {decision.get('agent', 'unknown')}\n"
        f"Domain: {decision.get('domain', 'unknown')}\n\n"
        "Was this drop correct despite the severity/confidence flags?"
    )
    try:
        result = await infer(prompt, system=_PROBE_SYSTEM)
        if result is None:
            return None
        raw = result.text.strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            return None
        data = json.loads(raw[start:end + 1])
        return {
            "correct_drop": data.get("correct_drop", False),
            "reason": data.get("reason", ""),
            "model": result.model,
        }
    except Exception as e:
        logger.warning("LLM probe failed: %s", str(e)[:60])
        return None


class DecisionSampler:
    """Polls the immutable ledger for decision records and audits a sample."""

    def __init__(
        self,
        ledger_url: str = "",
        ledger_token: str = "",
        sample_rate: float = 0.01,
        poll_interval: int = 60,
        max_verdicts_per_poll: int = 10,
    ):
        settings = get_settings()
        self._ledger_url = ledger_url or settings.ledger_url or ""
        self._ledger_token = ledger_token or settings.ledger_bearer_token or ""
        self._sample_rate = sample_rate
        self._poll_interval = poll_interval
        self._max_verdicts_per_poll = max_verdicts_per_poll
        self._last_seen_ts = 0
        self._audit_results: List[Dict] = []
        self._ledger = LedgerClient(url=self._ledger_url)

    async def poll_and_audit(self) -> List[Dict]:
        """Poll ledger for new decision records, sample drops, audit them."""
        if not self._ledger_url:
            return []

        entries = await self._fetch_new_entries()
        if not entries:
            return []

        auditable_with_corr = []
        for entry in entries:
            content = entry.get("content", {})
            if isinstance(content, str):
                content = json.loads(content)
            corr_id = entry.get("correlation_id", "")
            for d in content.get("decisions", []):
                if d.get("outcome") in ("drop", "suppress", "dedupe"):
                    d["domain"] = content.get("domain", "")
                    auditable_with_corr.append((d, corr_id))

        if not auditable_with_corr:
            return []

        sample_size = max(1, int(len(auditable_with_corr) * self._sample_rate))
        sample_size = min(sample_size, self._max_verdicts_per_poll)
        sampled = random.sample(auditable_with_corr, min(sample_size, len(auditable_with_corr)))

        verdicts = []
        for d, corr_id in sampled:
            v = audit_decision(d)
            if v["verdict"] == "FAILS":
                probe = await _llm_probe_decision(d)
                if probe is not None:
                    v["probe_result"] = probe
                    if probe["correct_drop"]:
                        v["verdict"] = "SURVIVES"
                        v["reason"] = f"LLM probe overrode deterministic FAIL: {probe['reason']}"
            verdicts.append(v)
            await self._write_verdict(v, corr_id)

        self._audit_results.extend(verdicts)
        if len(self._audit_results) > 1000:
            self._audit_results = self._audit_results[-1000:]

        return verdicts

    async def _fetch_new_entries(self) -> List[Dict]:
        """Fetch new decision.record entries from ledger since last poll."""
        try:
            async with httpx.AsyncClient(timeout=15, verify=False) as client:
                headers = {}
                if self._ledger_token:
                    headers["Authorization"] = f"Bearer {self._ledger_token}"

                url = f"{self._ledger_url.rstrip('/')}/api/entries"
                params: Dict[str, Any] = {
                    "entry_type": "decision.record",
                    "page_size": 100,
                }
                if self._last_seen_ts > 0:
                    params["from_ts"] = self._last_seen_ts + 1

                all_entries: List[Dict] = []
                while True:
                    resp = await client.get(url, params=params, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    entries = data if isinstance(data, list) else data.get("entries", [])
                    all_entries.extend(entries)
                    next_token = data.get("next_page_token", "") if isinstance(data, dict) else ""
                    if not next_token or len(all_entries) >= 500:
                        break
                    params["page_token"] = next_token

                if all_entries:
                    self._last_seen_ts = max(
                        e.get("written_ts", 0) for e in all_entries)

                return all_entries
        except Exception as e:
            logger.warning("Failed to fetch decision records: %s", str(e)[:60])
            return []

    async def _write_verdict(self, verdict: Dict, correlation_id: str) -> None:
        """Write audit verdict back to the ledger."""
        try:
            content = json.dumps(verdict, sort_keys=True, separators=(",", ":"))
            await self._ledger.write_entry(
                entry_type="audit.verdict",
                content=verdict,
                correlation_id=correlation_id,
            )
        except Exception as e:
            logger.warning("Failed to write audit verdict: %s", str(e)[:60])

    def get_results(self, limit: int = 50) -> List[Dict]:
        return self._audit_results[-limit:]

    def get_summary(self) -> Dict:
        total = len(self._audit_results)
        fails = sum(1 for r in self._audit_results if r.get("verdict") == "FAILS")
        survives = sum(1 for r in self._audit_results if r.get("verdict") == "SURVIVES")
        probed = sum(1 for r in self._audit_results if r.get("probe_result") is not None)
        overridden = sum(1 for r in self._audit_results
                         if (r.get("probe_result") or {}).get("correct_drop") is True)
        return {
            "total_audited": total,
            "survives": survives,
            "fails": fails,
            "disagreement_rate": round(fails / max(1, total), 3),
            "probed": probed,
            "llm_overrides": overridden,
            "last_seen_ts": self._last_seen_ts,
        }
