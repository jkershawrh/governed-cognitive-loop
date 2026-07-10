from __future__ import annotations

import pytest

from gcl.adapter.fleet_adapter import FleetAdapter
from gcl.adapter.intent_mapping import (
    AlertIntent,
    MigrateIntent,
    PreWarmIntent,
    ScaleIntent,
    ShedLoadIntent,
    map_action_to_intent,
)
from gcl.domain.contracts import ActionStep


def _scale_step(replicas=5, pool="default"):
    return ActionStep(
        step_index=0,
        action_type="scale",
        parameters={"replicas": replicas, "pool": pool},
    )


def _prewarm_step(target=3, pool="default"):
    return ActionStep(
        step_index=0,
        action_type="pre_warm",
        parameters={"target_replicas": target, "pool": pool},
    )


def _shed_step(max_inflight=50, duration=120):
    return ActionStep(
        step_index=0,
        action_type="shed_load",
        parameters={"max_inflight": max_inflight, "duration_seconds": duration},
    )


def _no_action_step():
    return ActionStep(step_index=0, action_type="no_action", parameters={})


class TestIntentMapping:
    def test_scale_action_maps_to_scale_intent(self):
        intent = map_action_to_intent(_scale_step(replicas=8), "corr-1")
        assert isinstance(intent, ScaleIntent)
        assert intent.desired_replicas == 8
        assert intent.pool == "default"
        assert intent.type == "scale"

    def test_scale_has_required_fleet_fields(self):
        intent = map_action_to_intent(_scale_step(replicas=5), "corr-1")
        assert intent.confidence > 0
        assert intent.horizon_seconds >= 0
        assert len(intent.justification) > 0
        assert intent.current_replicas >= 0

    def test_pre_warm_action_maps_to_pre_warm_intent(self):
        intent = map_action_to_intent(_prewarm_step(target=4), "corr-2")
        assert isinstance(intent, PreWarmIntent)
        assert intent.target_replicas == 4
        assert intent.model == "default"
        assert intent.type == "pre_warm"

    def test_shed_load_action_maps_to_shed_load_intent(self):
        intent = map_action_to_intent(_shed_step(max_inflight=25, duration=60), "corr-3")
        assert isinstance(intent, ShedLoadIntent)
        assert intent.max_inflight == 25
        assert intent.duration_seconds == 60
        assert intent.model == "default"
        assert intent.type == "shed_load"

    def test_no_action_emits_nothing(self):
        intent = map_action_to_intent(_no_action_step(), "corr-4")
        assert intent is None

    def test_unknown_action_emits_nothing(self):
        step = ActionStep(step_index=0, action_type="unknown", parameters={})
        intent = map_action_to_intent(step, "corr-5")
        assert intent is None

    def test_scale_with_custom_pool(self):
        step = _scale_step(replicas=3, pool="gpu-pool")
        intent = map_action_to_intent(step, "corr-6")
        assert isinstance(intent, ScaleIntent)
        assert intent.pool == "gpu-pool"

    def test_correlation_id_in_state_snapshot(self):
        intent = map_action_to_intent(_scale_step(5), "gcl-abc-123")
        assert intent.state_snapshot.get("correlation_id") == "gcl-abc-123"

    def test_serialized_schema_matches_fleet_llm_d(self):
        intent = map_action_to_intent(_scale_step(replicas=5), "corr-1")
        data = intent.model_dump()
        assert "type" in data
        assert "confidence" in data
        assert "horizon_seconds" in data
        assert "justification" in data
        assert "intent_type" not in data


    def test_alert_maps_to_alert_intent(self):
        step = ActionStep(
            step_index=0,
            action_type="alert",
            parameters={
                "severity": "critical",
                "message": "Compliance constraint active",
                "recommended_action": "migrate workloads",
            },
        )
        intent = map_action_to_intent(step, "corr-alert")
        assert isinstance(intent, AlertIntent)
        assert intent.severity == "critical"
        assert intent.message == "Compliance constraint active"
        assert intent.type == "alert"

    def test_migrate_maps_to_migrate_intent(self):
        step = ActionStep(
            step_index=0,
            action_type="migrate",
            parameters={
                "source_pool": "us-east",
                "target_pool": "eu-west",
                "model": "granite-3",
                "reason": "data residency",
            },
        )
        intent = map_action_to_intent(step, "corr-migrate")
        assert isinstance(intent, MigrateIntent)
        assert intent.source_pool == "us-east"
        assert intent.target_pool == "eu-west"
        assert intent.type == "migrate"


class TestFleetAdapter:
    @pytest.mark.asyncio
    async def test_actuate_scale_no_url(self):
        adapter = FleetAdapter(url="")
        result = await adapter.actuate(_scale_step(5), "corr-1")
        assert result is not None
        assert result["type"] == "scale"
        assert result["desired_replicas"] == 5

    @pytest.mark.asyncio
    async def test_actuate_no_action_returns_none(self):
        adapter = FleetAdapter(url="")
        result = await adapter.actuate(_no_action_step(), "corr-2")
        assert result is None

    @pytest.mark.asyncio
    async def test_actuate_prewarm(self):
        adapter = FleetAdapter(url="")
        result = await adapter.actuate(_prewarm_step(target=6), "corr-3")
        assert result is not None
        assert result["type"] == "pre_warm"
        assert result["target_replicas"] == 6
