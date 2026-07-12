from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

from gcl.domain.contracts import Evidence

logger = logging.getLogger(__name__)


class SignalSource:
    def measure(self) -> list[Evidence]:
        raise NotImplementedError


class FixtureSignalSource(SignalSource):
    def __init__(self, evidence: list[Evidence]):
        self._evidence = evidence

    def measure(self) -> list[Evidence]:
        return list(self._evidence)


class FleetMetricsSignalSource(SignalSource):
    """Pulls live metrics from fleet-llm-d platform metrics endpoint
    and converts them into Evidence objects for the GCL loop."""

    def __init__(self, fleet_url: Optional[str] = None, fleet_token: Optional[str] = None):
        from gcl.config import get_settings
        settings = get_settings()
        self._url = fleet_url or settings.fleet_url
        self._token = fleet_token or settings.fleet_token

    def measure(self) -> list[Evidence]:
        if not self._url:
            return []

        try:
            headers = {}
            if self._token:
                from gcl.adapter.fleet_adapter import _generate_fleet_token
                headers["Authorization"] = f"Bearer {_generate_fleet_token(self._token)}"

            resp = httpx.get(
                f"{self._url}/api/v1/metrics/platform",
                headers=headers,
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning("Fleet metrics returned %d", resp.status_code)
                return []

            data = resp.json()
            return self._convert_to_evidence(data)

        except (httpx.HTTPError, Exception) as e:
            logger.warning("Fleet metrics unavailable: %s", e)
            return []

    def _convert_to_evidence(self, data: dict) -> list[Evidence]:
        evidence: list[Evidence] = []

        inference = data.get("inference")
        if inference and inference.get("models"):
            for model_name, model_data in inference["models"].items():
                labels = {"model": model_name, "source_system": "inference"}
                if "latency_p95_ms" in model_data:
                    evidence.append(Evidence(
                        metric="latency_ms",
                        value=float(model_data["latency_p95_ms"]),
                        source="fleet_metrics",
                        labels={**labels, "percentile": "p95"},
                    ))
                if "replicas" in model_data:
                    evidence.append(Evidence(
                        metric="replicas",
                        value=float(model_data["replicas"]),
                        source="fleet_metrics",
                        labels=labels,
                    ))
                if "throughput_rps" in model_data:
                    evidence.append(Evidence(
                        metric="throughput_rps",
                        value=float(model_data["throughput_rps"]),
                        source="fleet_metrics",
                        labels=labels,
                    ))

        governance = data.get("governance")
        if governance:
            evidence.append(Evidence(
                metric="governance_commit_rate",
                value=float(governance.get("committed", 0)) / max(governance.get("total_cycles", 1), 1),
                source="fleet_metrics",
                labels={"source_system": "governance"},
            ))

        fleet = data.get("fleet")
        if fleet and fleet.get("routing") and fleet["routing"].get("semantic_tiers"):
            for tier, ratio in fleet["routing"]["semantic_tiers"].items():
                evidence.append(Evidence(
                    metric=f"semantic_tier_{tier}_ratio",
                    value=float(ratio),
                    source="fleet_metrics",
                    labels={"source_system": "routing"},
                ))

        ledger = data.get("ledger")
        if ledger:
            evidence.append(Evidence(
                metric="ledger_total_entries",
                value=float(ledger.get("total_entries", 0)),
                source="fleet_metrics",
                labels={"source_system": "ledger", "chains_valid": str(ledger.get("chains_valid", False))},
            ))

        return evidence
