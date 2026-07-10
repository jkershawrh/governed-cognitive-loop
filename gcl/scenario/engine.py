from __future__ import annotations

import random
from typing import Optional

from gcl.domain.contracts import Evidence


class ScenarioEngine:
    def __init__(self, scenario: str = "inference_fleet_spike", seed: int = 42):
        self._scenario = scenario
        self._seed = seed
        self._rng = random.Random(seed)
        self._steps: list[list[Evidence]] = []
        self._disturbance_step: int = -1
        self._build_scenario()

    def _build_scenario(self) -> None:
        if self._scenario == "inference_fleet_spike":
            self._build_inference_fleet_spike()
        elif self._scenario == "compliance_breach":
            self._build_compliance_breach()
        elif self._scenario == "capacity_exhaustion":
            self._build_capacity_exhaustion()
        elif self._scenario == "slo_cascade":
            self._build_slo_cascade()
        elif self._scenario == "mixed_storm":
            self._build_mixed_storm()
        else:
            self._build_inference_fleet_spike()

    def _build_inference_fleet_spike(self) -> None:
        self._disturbance_step = 4

        for step in range(8):
            signals: list[Evidence] = []

            if step <= 2:
                base_latency = 2000 + step * 500
                for i in range(12):
                    jitter = self._rng.uniform(-100, 100)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=base_latency + i * 30 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="replicas", value=3.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=10.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=450.0, source="billing"))

            elif step == 3:
                for i in range(12):
                    jitter = self._rng.uniform(-80, 120)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=4200 + i * 40 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="replicas", value=4.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=10.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=600.0, source="billing"))

            elif step == 4:
                for i in range(12):
                    jitter = self._rng.uniform(-200, 300)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=7500 + i * 80 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="replicas", value=4.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=1.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=800.0, source="billing"))

            elif step == 5:
                for i in range(12):
                    jitter = self._rng.uniform(-150, 150)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=5500 - i * 50 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="replicas", value=6.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=10.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=700.0, source="billing"))

            else:
                for i in range(12):
                    jitter = self._rng.uniform(-80, 80)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=3500 - (step - 5) * 300 + i * 20 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="replicas", value=5.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=10.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=500.0, source="billing"))

            self._steps.append(signals)

    def _build_compliance_breach(self) -> None:
        """6 steps: normal, then compliance violation at step 3, then recovery."""
        self._disturbance_step = 3

        for step in range(6):
            signals: list[Evidence] = []

            if step <= 2:
                base_latency = 2000 + step * 300
                for i in range(10):
                    jitter = self._rng.uniform(-80, 80)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=base_latency + i * 20 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="replicas", value=3.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=10.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=400.0, source="billing"))

            elif step == 3:
                base_latency = 2500
                for i in range(10):
                    jitter = self._rng.uniform(-80, 80)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=base_latency + i * 20 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="compliance_violation_flag", value=1.0, source="classification"))
                signals.append(Evidence(metric="data_residency_violation", value=1.0, source="classification"))
                signals.append(Evidence(metric="replicas", value=3.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=10.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=450.0, source="billing"))

            else:
                base_latency = 2200 + (step - 4) * 100
                for i in range(10):
                    jitter = self._rng.uniform(-60, 60)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=base_latency + i * 15 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="replicas", value=3.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=10.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=400.0, source="billing"))

            self._steps.append(signals)

    def _build_capacity_exhaustion(self) -> None:
        """8 steps: normal, then latency rising with capacity squeeze at step 3-4, then recovery."""
        self._disturbance_step = 4

        for step in range(8):
            signals: list[Evidence] = []

            if step <= 2:
                base_latency = 2000 + step * 400
                for i in range(10):
                    jitter = self._rng.uniform(-100, 100)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=base_latency + i * 25 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="replicas", value=4.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=10.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=500.0, source="billing"))

            elif step == 3:
                for i in range(10):
                    jitter = self._rng.uniform(-100, 150)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=5500 + i * 50 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="replicas", value=3.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=2.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=650.0, source="billing"))

            elif step == 4:
                for i in range(10):
                    jitter = self._rng.uniform(-150, 200)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=7000 + i * 60 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="replicas", value=1.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=1.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=750.0, source="billing"))

            elif step == 5:
                for i in range(10):
                    jitter = self._rng.uniform(-100, 100)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=5000 - i * 40 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="replicas", value=5.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=8.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=600.0, source="billing"))

            else:
                for i in range(10):
                    jitter = self._rng.uniform(-80, 80)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=3000 - (step - 5) * 200 + i * 15 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="replicas", value=4.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=10.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=500.0, source="billing"))

            self._steps.append(signals)

    def _build_slo_cascade(self) -> None:
        """8 steps: normal with low slo_breach, then rising severity + latency, then recovery."""
        self._disturbance_step = 4

        for step in range(8):
            signals: list[Evidence] = []

            if step <= 2:
                base_latency = 2500 + step * 300
                for i in range(10):
                    jitter = self._rng.uniform(-80, 80)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=base_latency + i * 20 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="slo_breach_severity", value=0.3, source="classification"))
                signals.append(Evidence(metric="replicas", value=3.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=10.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=450.0, source="billing"))

            elif step == 3:
                for i in range(10):
                    jitter = self._rng.uniform(-100, 120)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=4500 + i * 40 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="slo_breach_severity", value=0.65, source="classification"))
                signals.append(Evidence(metric="replicas", value=3.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=8.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=550.0, source="billing"))

            elif step == 4:
                for i in range(10):
                    jitter = self._rng.uniform(-120, 150)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=6000 + i * 60 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="slo_breach_severity", value=0.8, source="classification"))
                signals.append(Evidence(metric="replicas", value=4.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=6.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=650.0, source="billing"))

            elif step == 5:
                for i in range(10):
                    jitter = self._rng.uniform(-100, 130)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=7000 + i * 50 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="slo_breach_severity", value=0.9, source="classification"))
                signals.append(Evidence(metric="replicas", value=4.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=5.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=700.0, source="billing"))

            else:
                for i in range(10):
                    jitter = self._rng.uniform(-80, 80)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=3500 - (step - 5) * 250 + i * 15 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="slo_breach_severity", value=0.2, source="classification"))
                signals.append(Evidence(metric="replicas", value=4.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=10.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=450.0, source="billing"))

            self._steps.append(signals)

    def _build_mixed_storm(self) -> None:
        """8 steps: normal, then all classification signals fire at steps 3-4, then recovery."""
        self._disturbance_step = 3

        for step in range(8):
            signals: list[Evidence] = []

            if step <= 2:
                base_latency = 2000 + step * 400
                for i in range(10):
                    jitter = self._rng.uniform(-80, 80)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=base_latency + i * 25 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="replicas", value=4.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=10.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=500.0, source="billing"))

            elif step in (3, 4):
                for i in range(10):
                    jitter = self._rng.uniform(-150, 200)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=7000 + i * 70 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="slo_breach_severity", value=0.9, source="classification"))
                signals.append(Evidence(metric="capacity_pressure_score", value=0.85, source="classification"))
                signals.append(Evidence(metric="compliance_violation_flag", value=1.0, source="classification"))
                signals.append(Evidence(metric="replicas", value=2.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=2.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=800.0, source="billing"))

            else:
                for i in range(10):
                    jitter = self._rng.uniform(-80, 80)
                    signals.append(Evidence(
                        metric="latency_ms",
                        value=3500 - (step - 4) * 200 + i * 15 + jitter,
                        source="prometheus",
                    ))
                signals.append(Evidence(metric="replicas", value=5.0, source="kubernetes"))
                signals.append(Evidence(metric="max_replicas", value=10.0, source="kubernetes"))
                signals.append(Evidence(metric="hourly_cost", value=500.0, source="billing"))

            self._steps.append(signals)

    def get_step(self, index: int) -> list[Evidence]:
        if index < 0 or index >= len(self._steps):
            raise IndexError(f"Step {index} out of range (0-{len(self._steps) - 1})")
        return self._steps[index]

    def total_steps(self) -> int:
        return len(self._steps)

    def disturbance_step(self) -> int:
        return self._disturbance_step

    def metadata(self) -> dict:
        return {
            "scenario": self._scenario,
            "seed": self._seed,
            "total_steps": self.total_steps(),
            "disturbance_step": self._disturbance_step,
        }


_active_scenario: Optional[ScenarioEngine] = None


def seed_scenario(scenario: str = "inference_fleet_spike", seed: int = 42) -> ScenarioEngine:
    global _active_scenario
    _active_scenario = ScenarioEngine(scenario=scenario, seed=seed)
    return _active_scenario


def get_active_scenario() -> Optional[ScenarioEngine]:
    return _active_scenario


def clear_scenario() -> None:
    global _active_scenario
    _active_scenario = None
