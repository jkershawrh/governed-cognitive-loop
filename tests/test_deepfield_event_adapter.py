from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from gcl.adapter.deepfield_event_adapter import (
    DEEPFIELD_EVENT_SCHEMAS,
    DeepFieldCloudEventV1,
    deepfield_event_to_evidence,
)
from gcl.api.app import create_app
from gcl.api import routes
from gcl.config import get_settings
from gcl.domain.contracts import FalsificationResult
from gcl.domain.enums import Verdict


@pytest.fixture
async def client():
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as value:
        yield value


def _structured_event_request(payload: dict) -> dict:
    """Build the exact structured-CloudEvents request accepted by GCL."""
    return {
        "content": DeepFieldCloudEventV1.model_validate(payload).model_dump_json(),
        "headers": {"Content-Type": "application/cloudevents+json"},
    }


def _observation_event(*, expired: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    event_time = now - timedelta(hours=2) if expired else now
    expires_at = now - timedelta(hours=1) if expired else now + timedelta(hours=1)
    return {
        "specversion": "1.0",
        "id": "urn:sha256:" + "a" * 64,
        "source": "urn:srex:deepfield-fleet",
        "type": "io.srex.deepfield.observation.v1",
        "subject": "FleetInferencePool/primary",
        "time": event_time.isoformat(),
        "datacontenttype": "application/json",
        "dataschema": "urn:srex:deepfield:schema:observation:v1",
        "correlationid": "corr-deepfield-1",
        "causationid": "raw-signal-1",
        "idempotencykey": "deepfield-observation-1",
        "tenant": "tenant-a",
        "zone": "us-central",
        "traceparent": "00-11111111111111111111111111111111-2222222222222222-01",
        "expiresat": expires_at.isoformat(),
        "data": {
            "observation_id": "observation-1",
            "observed_at": event_time.isoformat(),
            "resource": {
                "cluster": "spoke-a",
                "namespace": "tenant-a",
                "kind": "FleetInferencePool",
                "name": "primary",
            },
            "signal_type": "latency_ms",
            "severity": "high",
            "value": 6200.0,
            "unit": "ms",
            "attributes": {},
            "evidence": [
                {
                    "uri": "urn:deepfield:evidence:observation-1",
                    "sha256": "b" * 64,
                    "media_type": "application/json",
                }
            ],
        },
    }


def _forecast_event() -> dict:
    now = datetime.now(timezone.utc)
    valid_until = now + timedelta(minutes=10)
    payload = _observation_event()
    payload.update(
        {
            "id": "urn:sha256:" + "c" * 64,
            "type": "io.srex.deepfield.forecast.v1",
            "subject": "FleetInferencePool/primary",
            "time": now.isoformat(),
            "dataschema": "urn:srex:deepfield:schema:forecast:v1",
            "correlationid": "corr-deepfield-forecast-1",
            "causationid": "finding-forecast-1",
            "idempotencykey": "deepfield-forecast-1",
            "expiresat": valid_until.isoformat(),
            "data": {
                "forecast_id": "forecast-1",
                "generated_at": now.isoformat(),
                "valid_until": valid_until.isoformat(),
                "horizon_seconds": 120,
                "forecast_type": "latency_ms",
                "target": {
                    "cluster": "spoke-a",
                    "namespace": "tenant-a",
                    "kind": "FleetInferencePool",
                    "name": "primary",
                },
                "predicted_value": 7000.0,
                "unit": "ms",
                "confidence": 0.82,
                "recommended_actions": ["fleet.scale"],
                "advisory_only": True,
                "model_version": "deepfield-fleet/test-v1",
                "input_digest": "d" * 64,
                "rejected_alternatives": ["fleet.shed_load"],
                "evidence": [
                    {
                        "uri": "urn:deepfield:evidence:forecast-1",
                        "sha256": "e" * 64,
                        "media_type": "application/json",
                    }
                ],
            },
        }
    )
    return payload


def _finding_event() -> dict:
    payload = _observation_event()
    payload.update(
        {
            "id": "urn:sha256:" + "f" * 64,
            "type": "io.srex.deepfield.finding.v1",
            "dataschema": "urn:srex:deepfield:schema:finding:v1",
            "data": {
                "finding_id": "finding-1",
                "created_at": payload["time"],
                "finding_type": "capacity_pressure",
                "severity": "high",
                "summary": "Capacity pressure is sustained.",
                "confidence": 0.8,
                "resources": [
                    {
                        "cluster": "spoke-a",
                        "namespace": "tenant-a",
                        "kind": "FleetInferencePool",
                        "name": "primary",
                    }
                ],
                "observation_ids": ["observation-1"],
                "attributes": {},
                "evidence": [
                    {
                        "uri": "urn:deepfield:evidence:finding-1",
                        "sha256": "b" * 64,
                        "media_type": "application/json",
                    }
                ],
            },
        }
    )
    return payload


def _remediation_event() -> dict:
    payload = _observation_event()
    payload.update(
        {
            "id": "urn:sha256:" + "9" * 64,
            "type": "io.srex.deepfield.remediation.proposal.v1",
            "dataschema": "urn:srex:deepfield:schema:remediation-proposal:v1",
            "data": {
                "proposal_id": "proposal-1",
                "requested_at": payload["time"],
                "target": {
                    "cluster": "spoke-a",
                    "namespace": "tenant-a",
                    "kind": "FleetInferencePool",
                    "name": "primary",
                },
                "action_class": "fleet.scale",
                "parameters": {"pool": "primary", "replicas": 4},
                "reason": "Forecast capacity exceeds the safe range.",
                "requested_by": "deepfield-fleet",
                "request_digest": "b" * 64,
                "confidence": 0.75,
                "advisory_only": True,
                "evidence": [
                    {
                        "uri": "urn:deepfield:evidence:proposal-1",
                        "sha256": "b" * 64,
                        "media_type": "application/json",
                    }
                ],
            },
        }
    )
    return payload


class TestDeepFieldEventConsumer:
    @pytest.mark.parametrize(
        ("factory", "expected_metric"),
        [
            (_observation_event, "latency_ms"),
            (_finding_event, "capacity_pressure"),
            (_forecast_event, "latency_ms"),
            (_remediation_event, "deepfield_remediation_fleet_scale"),
        ],
    )
    def test_all_pinned_event_identities_are_consumed(
        self,
        factory,
        expected_metric,
    ):
        event = DeepFieldCloudEventV1.model_validate(factory())
        evidence = deepfield_event_to_evidence(event)

        assert DEEPFIELD_EVENT_SCHEMAS[event.type] == event.dataschema
        assert evidence[0].metric == expected_metric

    def test_preserves_producer_identity_and_evidence_digest(self):
        event = DeepFieldCloudEventV1.model_validate(_observation_event())

        evidence = deepfield_event_to_evidence(event)

        assert len(evidence) == 1
        assert evidence[0].source == "deepfield-fleet"
        assert evidence[0].metric == "latency_ms"
        assert evidence[0].value == 6200.0
        assert evidence[0].labels["cluster"] == "spoke-a"
        assert evidence[0].metadata["producer_event_id"] == event.id
        assert evidence[0].metadata["producer_evidence_refs"] == ["sha256:" + "b" * 64]

    def test_rejects_type_schema_mismatch(self):
        payload = _observation_event()
        payload["dataschema"] = "urn:srex:deepfield:schema:forecast:v1"

        with pytest.raises(ValidationError, match="type and dataschema"):
            DeepFieldCloudEventV1.model_validate(payload)

    def test_rejects_payload_fields_outside_pinned_producer_schema(self):
        payload = _forecast_event()
        payload["data"]["execution_authorized"] = True

        with pytest.raises(ValidationError, match="Extra inputs"):
            DeepFieldCloudEventV1.model_validate(payload)

    def test_rejects_authoritative_or_scope_extended_forecast(self):
        authoritative = _forecast_event()
        authoritative["data"]["advisory_only"] = False
        with pytest.raises(ValidationError):
            DeepFieldCloudEventV1.model_validate(authoritative)

        extended = _forecast_event()
        extended["expiresat"] = (
            datetime.fromisoformat(extended["expiresat"]) + timedelta(minutes=1)
        ).isoformat()
        with pytest.raises(ValidationError, match="expiry must match"):
            DeepFieldCloudEventV1.model_validate(extended)

    @pytest.mark.asyncio
    async def test_api_accepts_event_and_preserves_scope(self, client):
        propose = AsyncMock(
            return_value={"status": "accepted", "execution_verified": False}
        )
        falsify = AsyncMock(
            return_value=FalsificationResult(
                action_id=uuid4(),
                verdict=Verdict.SURVIVES,
                reasoning="focused ingress scope fixture survives",
            )
        )
        with (
            patch.object(
                routes.get_driver()._adapter,
                "propose",
                propose,
            ),
            patch.object(
                routes.get_driver()._gate,
                "falsify",
                falsify,
            ),
            patch("gcl.classifier.classifier.get_force_rules", return_value=True),
            patch("gcl.interpreter.interpreter.get_force_rules", return_value=True),
            patch("gcl.falsification.gate.get_force_rules", return_value=True),
        ):
            response = await client.post(
                "/api/v1/events/deepfield",
                **_structured_event_request(_observation_event()),
            )

        assert response.status_code == 202
        assert response.json()["correlation_id"] == "corr-deepfield-1"
        assert response.json()["execution_verified"] is False
        signed = propose.await_args.args[0]
        assert signed.package.tenant == "tenant-a"
        assert signed.package.zone == "us-central"

    @pytest.mark.asyncio
    async def test_forecast_can_produce_a_scope_bound_signed_proposal(self, client):
        propose = AsyncMock(
            return_value={"status": "accepted", "execution_verified": False}
        )
        with (
            patch.object(
                routes.get_driver()._adapter,
                "propose",
                propose,
            ),
            patch.object(
                routes.get_driver()._accountability,
                "can_commit",
                return_value=(True, ""),
            ),
            patch("gcl.classifier.classifier.get_force_rules", return_value=True),
            patch("gcl.interpreter.interpreter.get_force_rules", return_value=True),
            patch("gcl.falsification.gate.get_force_rules", return_value=True),
        ):
            response = await client.post(
                "/api/v1/events/deepfield",
                **_structured_event_request(_forecast_event()),
            )

        assert response.status_code == 202
        assert response.json()["proposal_status"] == "accepted"
        assert response.json()["decision_package_digest"]
        signed = propose.await_args.args[0]
        assert signed.package.tenant == "tenant-a"
        assert signed.package.zone == "us-central"
        assert signed.package.confidence == 0.82
        lifetime = (
            signed.package.expires_at - signed.package.created_at
        ).total_seconds()
        assert 0 < lifetime <= 120

    @pytest.mark.asyncio
    async def test_api_rejects_expired_event(self, client):
        response = await client.post(
            "/api/v1/events/deepfield",
            **_structured_event_request(_observation_event(expired=True)),
        )

        assert response.status_code == 410

    @pytest.mark.asyncio
    async def test_api_rejects_untrusted_source(self, client):
        payload = _observation_event()
        payload["source"] = "urn:example:not-deepfield"

        response = await client.post(
            "/api/v1/events/deepfield", **_structured_event_request(payload)
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_production_requires_configured_sink_credential(
        self,
        client,
        monkeypatch,
    ):
        monkeypatch.setenv("GCL_RUNTIME_MODE", "production")
        monkeypatch.delenv("GCL_DEEPFIELD_EVENT_BEARER_TOKEN", raising=False)
        get_settings.cache_clear()

        response = await client.post(
            "/api/v1/events/deepfield",
            **_structured_event_request(_observation_event()),
        )

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_configured_sink_credential_is_verified(
        self,
        client,
        monkeypatch,
    ):
        monkeypatch.setenv("GCL_DEEPFIELD_EVENT_BEARER_TOKEN", "deepfield-token")
        get_settings.cache_clear()

        rejected = await client.post(
            "/api/v1/events/deepfield",
            content=DeepFieldCloudEventV1.model_validate(
                _observation_event()
            ).model_dump_json(),
            headers={
                "Authorization": "Bearer wrong",
                "Content-Type": "application/cloudevents+json",
            },
        )

        assert rejected.status_code == 401

    @pytest.mark.asyncio
    async def test_api_rejects_non_cloudevents_media_type(self, client):
        response = await client.post(
            "/api/v1/events/deepfield",
            json=_observation_event(),
        )

        assert response.status_code == 415
