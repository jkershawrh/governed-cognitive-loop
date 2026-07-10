from __future__ import annotations

import pytest

from gcl.scenario.engine import ScenarioEngine, clear_scenario, get_active_scenario, seed_scenario


class TestScenarioEngine:
    def test_deterministic_seed(self):
        e1 = ScenarioEngine(seed=42)
        e2 = ScenarioEngine(seed=42)
        for i in range(e1.total_steps()):
            s1 = e1.get_step(i)
            s2 = e2.get_step(i)
            assert len(s1) == len(s2)
            for a, b in zip(s1, s2):
                assert a.metric == b.metric
                assert a.value == b.value

    def test_total_steps(self):
        engine = ScenarioEngine()
        assert engine.total_steps() == 8

    def test_disturbance_step(self):
        engine = ScenarioEngine()
        assert engine.disturbance_step() == 4

    def test_step_has_latency_signals(self):
        engine = ScenarioEngine()
        for i in range(engine.total_steps()):
            signals = engine.get_step(i)
            latency_signals = [s for s in signals if s.metric == "latency_ms"]
            assert len(latency_signals) >= 10

    def test_disturbance_step_has_high_latency(self):
        engine = ScenarioEngine()
        signals = engine.get_step(engine.disturbance_step())
        latency_signals = [s for s in signals if s.metric == "latency_ms"]
        avg = sum(s.value for s in latency_signals) / len(latency_signals)
        assert avg > 7000

    def test_disturbance_step_has_low_max_replicas(self):
        engine = ScenarioEngine()
        signals = engine.get_step(engine.disturbance_step())
        max_rep = [s for s in signals if s.metric == "max_replicas"]
        assert len(max_rep) == 1
        assert max_rep[0].value <= 2.0

    def test_normal_step_has_low_latency(self):
        engine = ScenarioEngine()
        signals = engine.get_step(0)
        latency_signals = [s for s in signals if s.metric == "latency_ms"]
        avg = sum(s.value for s in latency_signals) / len(latency_signals)
        assert avg < 4000

    def test_out_of_range_raises(self):
        engine = ScenarioEngine()
        with pytest.raises(IndexError):
            engine.get_step(99)

    def test_metadata(self):
        engine = ScenarioEngine(scenario="inference_fleet_spike", seed=99)
        meta = engine.metadata()
        assert meta["scenario"] == "inference_fleet_spike"
        assert meta["seed"] == 99
        assert meta["total_steps"] == 8
        assert meta["disturbance_step"] == 4


class TestComplianceBreachScenario:
    def test_compliance_breach_scenario(self):
        engine = ScenarioEngine(scenario="compliance_breach")
        assert engine.total_steps() == 6
        assert engine.disturbance_step() == 3

    def test_compliance_breach_step3_has_compliance_flag(self):
        engine = ScenarioEngine(scenario="compliance_breach")
        signals = engine.get_step(3)
        compliance = [s for s in signals if s.metric == "compliance_violation_flag"]
        assert len(compliance) >= 1
        assert compliance[0].value == 1.0


class TestCapacityExhaustionScenario:
    def test_capacity_exhaustion_scenario(self):
        engine = ScenarioEngine(scenario="capacity_exhaustion")
        assert engine.total_steps() == 8
        assert engine.disturbance_step() == 4

    def test_capacity_exhaustion_step4(self):
        engine = ScenarioEngine(scenario="capacity_exhaustion")
        signals = engine.get_step(4)
        latency_signals = [s for s in signals if s.metric == "latency_ms"]
        avg_lat = sum(s.value for s in latency_signals) / len(latency_signals)
        assert avg_lat > 6000
        max_rep = [s for s in signals if s.metric == "max_replicas"]
        assert len(max_rep) >= 1
        assert max_rep[0].value <= 1


class TestSloCascadeScenario:
    def test_slo_cascade_scenario(self):
        engine = ScenarioEngine(scenario="slo_cascade")
        assert engine.total_steps() == 8
        assert engine.disturbance_step() == 4

    def test_slo_cascade_step4_has_slo_breach(self):
        engine = ScenarioEngine(scenario="slo_cascade")
        signals = engine.get_step(4)
        slo = [s for s in signals if s.metric == "slo_breach_severity"]
        assert len(slo) >= 1
        assert slo[0].value > 0.6


class TestMixedStormScenario:
    def test_mixed_storm_scenario(self):
        engine = ScenarioEngine(scenario="mixed_storm")
        assert engine.total_steps() == 8
        assert engine.disturbance_step() == 3

    def test_mixed_storm_step3_has_all_signals(self):
        engine = ScenarioEngine(scenario="mixed_storm")
        signals = engine.get_step(3)
        metrics = {s.metric for s in signals}
        assert "slo_breach_severity" in metrics
        assert "capacity_pressure_score" in metrics
        assert "compliance_violation_flag" in metrics


class TestMultiClusterMigrationScenario:
    def test_multi_cluster_scenario(self):
        engine = ScenarioEngine(scenario="multi_cluster_migration")
        assert engine.total_steps() == 8
        assert engine.disturbance_step() == 4

    def test_step3_has_capacity_exhaustion(self):
        engine = ScenarioEngine(scenario="multi_cluster_migration")
        signals = engine.get_step(3)
        max_rep = [s for s in signals if s.metric == "max_replicas"]
        assert len(max_rep) >= 1
        assert max_rep[0].value <= 0

    def test_step4_has_compliance_violation(self):
        engine = ScenarioEngine(scenario="multi_cluster_migration")
        signals = engine.get_step(4)
        compliance = [s for s in signals if s.metric == "compliance_violation_flag"]
        assert len(compliance) >= 1
        assert compliance[0].value == 1.0

    def test_step0_has_cluster_labels(self):
        engine = ScenarioEngine(scenario="multi_cluster_migration")
        signals = engine.get_step(0)
        labeled = [s for s in signals if s.labels.get("cluster")]
        assert len(labeled) > 0


class TestScenarioGlobals:
    def test_seed_and_get(self):
        clear_scenario()
        assert get_active_scenario() is None
        engine = seed_scenario("inference_fleet_spike", 42)
        assert get_active_scenario() is engine
        clear_scenario()
        assert get_active_scenario() is None
