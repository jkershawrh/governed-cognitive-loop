from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from gcl.api.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self, client):
        response = await client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestCycleEndpoint:
    @pytest.mark.asyncio
    async def test_cycle_returns_response(self, client):
        with patch("gcl.classifier.classifier.get_force_rules", return_value=True), \
             patch("gcl.interpreter.interpreter.get_force_rules", return_value=True), \
             patch("gcl.falsification.gate.get_force_rules", return_value=True):
            response = await client.post(
                "/api/v1/cycle",
                json={
                    "signals": [
                        {"metric": "latency_ms", "value": 6000.0},
                    ]
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert "cycle_id" in data
        assert "correlation_id" in data
        assert "committed" in data

    @pytest.mark.asyncio
    async def test_cycle_inspection(self, client):
        with patch("gcl.classifier.classifier.get_force_rules", return_value=True), \
             patch("gcl.interpreter.interpreter.get_force_rules", return_value=True), \
             patch("gcl.falsification.gate.get_force_rules", return_value=True):
            create_resp = await client.post(
                "/api/v1/cycle",
                json={"signals": [{"metric": "latency_ms", "value": 6000.0}]},
            )
        cycle_id = create_resp.json()["cycle_id"]

        response = await client.get(f"/api/v1/cycles/{cycle_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["correlation_id"] == create_resp.json()["correlation_id"]

    @pytest.mark.asyncio
    async def test_cycle_not_found(self, client):
        response = await client.get("/api/v1/cycles/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_chain_endpoint(self, client):
        with patch("gcl.classifier.classifier.get_force_rules", return_value=True), \
             patch("gcl.interpreter.interpreter.get_force_rules", return_value=True), \
             patch("gcl.falsification.gate.get_force_rules", return_value=True):
            create_resp = await client.post(
                "/api/v1/cycle",
                json={"signals": [{"metric": "latency_ms", "value": 6000.0}]},
            )
        cycle_id = create_resp.json()["cycle_id"]

        response = await client.get(f"/api/v1/cycles/{cycle_id}/chain")
        assert response.status_code == 200
        entries = response.json()
        assert len(entries) > 0
        entry_types = {e["entry_type"] for e in entries}
        assert "gcl.classify" in entry_types

    @pytest.mark.asyncio
    async def test_chain_not_found(self, client):
        response = await client.get("/api/v1/cycles/nonexistent/chain")
        assert response.status_code == 404


class TestListCycles:
    @pytest.mark.asyncio
    async def test_list_cycles(self, client):
        with patch("gcl.classifier.classifier.get_force_rules", return_value=True), \
             patch("gcl.interpreter.interpreter.get_force_rules", return_value=True), \
             patch("gcl.falsification.gate.get_force_rules", return_value=True):
            await client.post(
                "/api/v1/cycle",
                json={"signals": [{"metric": "latency_ms", "value": 6000.0}]},
            )
        response = await client.get("/api/v1/cycles")
        assert response.status_code == 200
        cycles = response.json()
        assert len(cycles) >= 1


class TestReset:
    @pytest.mark.asyncio
    async def test_reset(self, client):
        response = await client.post("/api/v1/reset")
        assert response.status_code == 200
        assert response.json() == {"status": "reset"}


class TestScenarioEndpoints:
    @pytest.mark.asyncio
    async def test_seed_scenario(self, client):
        response = await client.post(
            "/api/v1/scenario/seed",
            json={"scenario": "inference_fleet_spike", "seed": 42},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_steps"] == 8
        assert data["disturbance_step"] == 4

    @pytest.mark.asyncio
    async def test_get_scenario_step(self, client):
        await client.post(
            "/api/v1/scenario/seed",
            json={"scenario": "inference_fleet_spike", "seed": 42},
        )
        response = await client.get("/api/v1/scenario/step/0")
        assert response.status_code == 200
        data = response.json()
        assert data["step_index"] == 0
        assert len(data["signals"]) > 10

    @pytest.mark.asyncio
    async def test_scenario_step_not_seeded(self, client):
        await client.post("/api/v1/reset")
        response = await client.get("/api/v1/scenario/step/0")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_scenario_step_out_of_range(self, client):
        await client.post(
            "/api/v1/scenario/seed",
            json={"scenario": "inference_fleet_spike", "seed": 42},
        )
        response = await client.get("/api/v1/scenario/step/99")
        assert response.status_code == 404
