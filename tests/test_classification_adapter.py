from __future__ import annotations

from gcl.adapter.classification_adapter import (
    batch_classifications_to_evidence,
    classification_to_evidence,
)


class TestClassificationAdapter:
    def test_slo_breach_to_evidence(self):
        record = {
            "class_name": "slo_breach_predicted",
            "confidence": 0.85,
            "severity": "high",
            "taxonomy": "slo",
            "agent_name": "slo_agent",
        }
        results = classification_to_evidence(record)
        primary = [e for e in results if e.metric == "slo_breach_severity"]
        assert len(primary) == 1
        assert primary[0].value == 0.85
        assert primary[0].source == "deepfield-fleet"

    def test_capacity_pressure_to_evidence(self):
        record = {
            "class_name": "capacity_saturated",
            "confidence": 0.9,
            "severity": "critical",
            "taxonomy": "capacity",
            "agent_name": "cap_agent",
        }
        results = classification_to_evidence(record)
        primary = [e for e in results if e.metric == "capacity_pressure_score"]
        assert len(primary) == 1
        assert primary[0].value == 0.9

    def test_compliance_violation_to_evidence(self):
        record = {
            "class_name": "policy_violation",
            "confidence": 0.95,
            "severity": "critical",
            "taxonomy": "compliance",
            "agent_name": "comp_agent",
        }
        results = classification_to_evidence(record)
        primary = [e for e in results if e.metric == "compliance_violation_flag"]
        assert len(primary) == 1
        assert primary[0].value == 1.0

    def test_contributing_metrics_preserved(self):
        record = {
            "class_name": "slo_breach_predicted",
            "confidence": 0.8,
            "metrics": {"forecast_value": 6200.0, "slope_per_minute": 12.3},
        }
        results = classification_to_evidence(record)
        metric_names = {e.metric for e in results}
        assert "forecast_value" in metric_names
        assert "slope_per_minute" in metric_names
        forecast = [e for e in results if e.metric == "forecast_value"][0]
        assert forecast.value == 6200.0
        slope = [e for e in results if e.metric == "slope_per_minute"][0]
        assert slope.value == 12.3

    def test_unknown_classification_passthrough(self):
        record = {
            "class_name": "unknown_class",
            "confidence": 0.7,
            "severity": "low",
        }
        results = classification_to_evidence(record)
        primary = [e for e in results if e.metric == "classification_unknown_class"]
        assert len(primary) == 1

    def test_labels_preserved(self):
        record = {
            "class_name": "slo_breach_predicted",
            "confidence": 0.8,
            "severity": "high",
            "taxonomy": "slo",
            "agent_name": "slo_agent",
        }
        results = classification_to_evidence(record)
        primary = [e for e in results if e.metric == "slo_breach_severity"][0]
        assert primary.labels["class_name"] == "slo_breach_predicted"
        assert primary.labels["severity"] == "high"
        assert primary.labels["taxonomy"] == "slo"
        assert primary.labels["agent_name"] == "slo_agent"

    def test_slo_breach_emits_forecast_value_as_latency(self):
        record = {
            "class_name": "slo_breach_predicted",
            "severity": "critical",
            "confidence": 0.92,
            "metrics": {"forecast_value": 6200.0, "slope_per_minute": 12.3},
        }
        evidence = classification_to_evidence(record)
        latency = [e for e in evidence if e.metric == "latency_ms"]
        assert len(latency) >= 1, "Should emit forecast_value as latency_ms"
        assert latency[0].value == 6200.0

    def test_slo_breach_without_forecast_value_still_works(self):
        record = {
            "class_name": "slo_breach_predicted",
            "severity": "high",
            "confidence": 0.8,
            "metrics": {},
        }
        evidence = classification_to_evidence(record)
        assert len(evidence) >= 1
        slo = [e for e in evidence if e.metric == "slo_breach_severity"]
        assert len(slo) == 1
        latency = [e for e in evidence if e.metric == "latency_ms"]
        assert len(latency) == 0  # No forecast_value, no latency evidence

    def test_semantic_tier_to_evidence(self):
        record = {
            "class_name": "semantic_tier_simple",
            "severity": "info",
            "confidence": 0.75,
        }
        evidence = classification_to_evidence(record)
        tier_ev = [e for e in evidence if "semantic_tier" in e.metric]
        assert len(tier_ev) >= 1
        assert tier_ev[0].value == 0.75

    def test_batch_conversion(self):
        records = [
            {"class_name": "slo_breach_predicted", "confidence": 0.8},
            {"class_name": "capacity_saturated", "confidence": 0.9},
            {"class_name": "policy_violation", "confidence": 0.95},
        ]
        results = batch_classifications_to_evidence(records)
        assert isinstance(results, list)
        metric_names = {e.metric for e in results}
        assert "slo_breach_severity" in metric_names
        assert "capacity_pressure_score" in metric_names
        assert "compliance_violation_flag" in metric_names
