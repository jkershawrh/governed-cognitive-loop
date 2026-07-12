from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gcl.loop.signals import FleetMetricsSignalSource, FixtureSignalSource
from gcl.domain.contracts import Evidence


class TestFixtureSignalSource:
    def test_returns_evidence(self):
        evidence = [Evidence(metric="latency_ms", value=1000.0)]
        source = FixtureSignalSource(evidence)
        result = source.measure()
        assert len(result) == 1
        assert result[0].metric == "latency_ms"


class TestFleetMetricsSignalSource:
    def test_converts_inference_metrics(self):
        source = FleetMetricsSignalSource(fleet_url="http://fake")
        data = {
            "inference": {
                "models": {
                    "granite-3.2-sovereign": {
                        "replicas": 8,
                        "latency_p95_ms": 1200.0,
                        "throughput_rps": 2.6,
                        "status": "healthy",
                    }
                }
            }
        }
        evidence = source._convert_to_evidence(data)
        latency = [e for e in evidence if e.metric == "latency_ms"]
        assert len(latency) >= 1
        assert latency[0].value == 1200.0
        assert latency[0].labels.get("model") == "granite-3.2-sovereign"

    def test_converts_governance_metrics(self):
        source = FleetMetricsSignalSource(fleet_url="http://fake")
        data = {
            "governance": {
                "total_cycles": 100,
                "committed": 75,
                "rejected": 25,
            }
        }
        evidence = source._convert_to_evidence(data)
        commit_rate = [e for e in evidence if e.metric == "governance_commit_rate"]
        assert len(commit_rate) == 1
        assert commit_rate[0].value == 0.75

    def test_converts_semantic_tiers(self):
        source = FleetMetricsSignalSource(fleet_url="http://fake")
        data = {
            "fleet": {
                "routing": {
                    "semantic_tiers": {
                        "simple": 0.6,
                        "complex": 0.4,
                    }
                }
            }
        }
        evidence = source._convert_to_evidence(data)
        tiers = [e for e in evidence if "semantic_tier" in e.metric]
        assert len(tiers) == 2

    def test_converts_ledger_metrics(self):
        source = FleetMetricsSignalSource(fleet_url="http://fake")
        data = {
            "ledger": {
                "total_entries": 1253,
                "chains_valid": True,
            }
        }
        evidence = source._convert_to_evidence(data)
        ledger = [e for e in evidence if e.metric == "ledger_total_entries"]
        assert len(ledger) == 1
        assert ledger[0].value == 1253.0

    def test_empty_data_returns_empty(self):
        source = FleetMetricsSignalSource(fleet_url="http://fake")
        evidence = source._convert_to_evidence({})
        assert evidence == []

    def test_no_url_returns_empty(self):
        source = FleetMetricsSignalSource(fleet_url="")
        result = source.measure()
        assert result == []
