from __future__ import annotations

from typing import Any

from gcl.domain.contracts import Evidence

_SLO_CLASSES = {
    "slo_breach_predicted", "slo_breach_imminent", "slo_degraded",
}

_CAPACITY_CLASSES = {
    "capacity_saturated", "capacity_pressure", "capacity_elevated",
}

_COMPLIANCE_CLASSES = {
    "policy_violation", "compliance_violation",
}

_SEVERITY_SCORES = {
    "info": 0.1,
    "low": 0.3,
    "medium": 0.5,
    "high": 0.8,
    "critical": 1.0,
}


def classification_to_evidence(record: dict[str, Any]) -> list[Evidence]:
    """Transform a deepfield-fleet ClassificationRecord dict into GCL Evidence objects."""
    results: list[Evidence] = []

    class_name = record.get("class_name", "")
    severity = record.get("severity", "info")
    confidence = float(record.get("confidence", 0.5))
    taxonomy = record.get("taxonomy", "")
    agent_name = record.get("agent_name", "")
    rationale = record.get("rationale", "")
    record_metrics = record.get("metrics", {})
    record_labels = record.get("labels", {})

    common_labels = {
        "class_name": class_name,
        "severity": severity,
        "taxonomy": taxonomy,
        "agent_name": agent_name,
    }
    common_metadata = {
        "rationale": rationale,
        "source_classification_id": str(record.get("classification_id", "")),
    }

    if class_name in _SLO_CLASSES:
        results.append(Evidence(
            metric="slo_breach_severity",
            value=confidence,
            source="classification",
            labels=common_labels,
            metadata=common_metadata,
        ))
    elif class_name in _CAPACITY_CLASSES:
        results.append(Evidence(
            metric="capacity_pressure_score",
            value=confidence,
            source="classification",
            labels=common_labels,
            metadata=common_metadata,
        ))
    elif class_name in _COMPLIANCE_CLASSES:
        results.append(Evidence(
            metric="compliance_violation_flag",
            value=1.0,
            source="classification",
            labels=common_labels,
            metadata=common_metadata,
        ))
    else:
        severity_score = _SEVERITY_SCORES.get(severity, 0.5)
        results.append(Evidence(
            metric=f"classification_{class_name}",
            value=severity_score * confidence,
            source="classification",
            labels=common_labels,
            metadata=common_metadata,
        ))

    for metric_name, metric_value in record_metrics.items():
        try:
            results.append(Evidence(
                metric=metric_name,
                value=float(metric_value),
                source="classification_metrics",
                labels={"contributing_to": class_name},
            ))
        except (TypeError, ValueError):
            pass

    return results


def batch_classifications_to_evidence(records: list[dict[str, Any]]) -> list[Evidence]:
    """Transform a list of ClassificationRecords into a flat list of Evidence."""
    results: list[Evidence] = []
    for record in records:
        results.extend(classification_to_evidence(record))
    return results
