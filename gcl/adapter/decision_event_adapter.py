"""Generic decision event adapter.

Converts decision records from any system into GCL Evidence for falsification.
Domain-agnostic — does not know what system produced the decision.
Uses the decision-record.json schema contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from gcl.domain.contracts import Evidence


def decision_to_evidence(decision: Dict[str, Any], system_id: str = "") -> Evidence:
    """Convert a single decision from a decision record into GCL Evidence.

    The decision dict follows the decision-record.json schema:
        subject_id, subject_type, severity, outcome, agent, confidence, ...
    """
    return Evidence(
        metric="decision.outcome",
        value=decision.get("confidence", 0.0),
        timestamp=datetime.now(timezone.utc),
        source=system_id or "unknown",
        labels={
            "subject_type": decision.get("subject_type", ""),
            "severity": decision.get("severity", ""),
            "outcome": decision.get("outcome", ""),
            "agent": decision.get("agent", ""),
            "tier": decision.get("tier", ""),
        },
        metadata={
            "subject_id": decision.get("subject_id", ""),
            "namespace": decision.get("namespace", ""),
            "evidence": decision.get("evidence", ""),
        },
    )


def decision_record_to_evidence(record: Dict[str, Any]) -> List[Evidence]:
    """Convert a full decision record (batch) into a list of Evidence.

    Only converts decisions with drop/suppress/dedupe outcomes — these are
    the ones worth auditing. Keep/escalate decisions are not challenged.
    """
    system_id = record.get("system_id", "")
    auditable_outcomes = {"drop", "suppress", "dedupe"}

    return [
        decision_to_evidence(d, system_id)
        for d in record.get("decisions", [])
        if d.get("outcome", "") in auditable_outcomes
    ]
