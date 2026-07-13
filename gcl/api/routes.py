from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gcl.adapter.classification_adapter import batch_classifications_to_evidence
from gcl.api.schemas import ChainEntry, CycleRequest, CycleResponse
from gcl.domain.contracts import Evidence, LoopCycle
from gcl.domain.decision_package import (
    decision_package_cloud_event_schema,
    decision_package_schema,
)
from gcl.loop.driver import LoopDriver
from gcl.loop.ledger import LedgerClient
from gcl.scenario.engine import (
    clear_scenario,
    get_active_scenario,
    seed_scenario,
)

router = APIRouter(prefix="/api/v1")

_ledger = LedgerClient()
_driver = LoopDriver(ledger=_ledger)
_cycles: dict[str, LoopCycle] = {}


def _proposal_status(cycle: LoopCycle) -> str | None:
    if not cycle.proposal_response:
        return None
    value = cycle.proposal_response.get("status")
    return str(value) if value is not None else None


def get_driver() -> LoopDriver:
    return _driver


def get_ledger() -> LedgerClient:
    return _ledger


@router.post("/cycle", response_model=CycleResponse)
async def run_cycle(request: CycleRequest) -> CycleResponse:
    signals = [
        Evidence(metric=s.metric, value=s.value, source=s.source)
        for s in request.signals
    ]

    cycle = await _driver.run_cycle(signals)
    _cycles[str(cycle.cycle_id)] = cycle

    action_type = None
    if cycle.action_plan is not None:
        committed = cycle.action_plan.steps[cycle.action_plan.committed_step_index]
        action_type = committed.action_type

    verdict = None
    if cycle.falsification is not None:
        verdict = cycle.falsification.verdict.value

    return CycleResponse(
        cycle_id=str(cycle.cycle_id),
        correlation_id=cycle.correlation_id,
        committed=cycle.committed,
        execution_verified=cycle.execution_verified,
        proposal_status=_proposal_status(cycle),
        decision_package_digest=cycle.decision_package_digest,
        action_type=action_type,
        falsification_verdict=verdict,
    )


@router.get("/cycles/{cycle_id}")
async def get_cycle(cycle_id: str) -> dict:
    cycle = _cycles.get(cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail="Cycle not found")
    return cycle.model_dump(mode="json")


@router.get("/cycles/{cycle_id}/chain", response_model=list[ChainEntry])
async def get_chain(cycle_id: str) -> list[ChainEntry]:
    cycle = _cycles.get(cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail="Cycle not found")

    entries = await _ledger.query_chain(cycle.correlation_id)
    result = []
    for e in entries:
        content = e.get("content", {})
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                content = {"raw": content}
        result.append(ChainEntry(
            entry_id=e.get("entry_id", ""),
            entry_type=e.get("entry_type", ""),
            correlation_id=e.get("correlation_id", ""),
            content=content,
        ))
    return result


@router.get("/cycles")
async def list_cycles() -> list[CycleResponse]:
    results = []
    for cycle in _cycles.values():
        action_type = None
        if cycle.action_plan is not None:
            committed = cycle.action_plan.steps[cycle.action_plan.committed_step_index]
            action_type = committed.action_type
        verdict = None
        if cycle.falsification is not None:
            verdict = cycle.falsification.verdict.value
        results.append(CycleResponse(
            cycle_id=str(cycle.cycle_id),
            correlation_id=cycle.correlation_id,
            committed=cycle.committed,
            execution_verified=cycle.execution_verified,
            proposal_status=_proposal_status(cycle),
            decision_package_digest=cycle.decision_package_digest,
            action_type=action_type,
            falsification_verdict=verdict,
        ))
    return results


@router.get("/contracts/decision-package-v1/schema")
async def get_decision_package_schema() -> dict:
    return decision_package_schema()


@router.get("/contracts/decision-package-cloudevent-v1/schema")
async def get_decision_package_cloud_event_schema() -> dict:
    return decision_package_cloud_event_schema()


@router.post("/reset")
async def reset() -> dict:
    global _ledger, _driver, _cycles
    _cycles.clear()
    _ledger._memory.clear()
    clear_scenario()
    return {"status": "reset"}


class ScenarioSeedRequest(BaseModel):
    scenario: str = "inference_fleet_spike"
    seed: int = 42


@router.post("/scenario/seed")
async def seed_scenario_endpoint(request: ScenarioSeedRequest) -> dict:
    engine = seed_scenario(request.scenario, request.seed)
    return engine.metadata()


@router.get("/scenario/step/{step_index}")
async def get_scenario_step(step_index: int) -> dict:
    engine = get_active_scenario()
    if engine is None:
        raise HTTPException(status_code=400, detail="No scenario seeded. POST /api/v1/scenario/seed first.")
    try:
        signals = engine.get_step(step_index)
    except IndexError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "step_index": step_index,
        "signals": [
            {"metric": s.metric, "value": s.value, "source": s.source}
            for s in signals
        ],
    }


@router.get("/modelplane/status")
async def modelplane_status() -> dict:
    """Fetch cluster and deployment state from fleet-controller ModelPlane endpoints."""
    import os

    fleet_url = os.environ.get("GCL_FLEET_URL", "")
    if not fleet_url:
        return {"clusters": [], "deployments": [], "error": "GCL_FLEET_URL not configured"}

    import httpx

    from gcl.adapter.fleet_adapter import _generate_fleet_token
    from gcl.config import get_settings

    settings = get_settings()
    headers: dict[str, str] = {}
    if settings.fleet_token:
        if (
            settings.runtime_mode == "production"
            or not settings.allow_legacy_fleet_hmac_development_compat
        ):
            return {
                "clusters": [],
                "deployments": [],
                "error": "legacy fleet HMAC compatibility is disabled",
            }
        headers["Authorization"] = f"Bearer {_generate_fleet_token(settings.fleet_token)}"

    result: dict = {"clusters": [], "deployments": []}
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{fleet_url}/api/v1/modelplane/clusters", headers=headers)
            if r.status_code == 200:
                result["clusters"] = r.json()
        except Exception:
            pass
        try:
            r = await client.get(f"{fleet_url}/api/v1/modelplane/deployments", headers=headers)
            if r.status_code == 200:
                result["deployments"] = r.json()
        except Exception:
            pass
    return result


@router.post("/classify-prompt")
async def classify_prompt(request: dict) -> dict:
    from gcl.classifier.prompt_classifier import PromptClassifier
    classifier = PromptClassifier()
    prompt = request.get("prompt", "")
    result = classifier.classify(prompt)
    return result.model_dump()


@router.post("/cycle/metrics")
async def cycle_from_metrics() -> CycleResponse:
    """Pull live platform metrics from fleet-llm-d and run a governed cycle."""
    from gcl.loop.signals import FleetMetricsSignalSource
    source = FleetMetricsSignalSource()
    signals = source.measure()

    if not signals:
        raise HTTPException(status_code=503, detail="No metrics available from fleet-llm-d")

    cycle = await _driver.run_cycle(signals)
    _cycles[str(cycle.cycle_id)] = cycle

    action_type = None
    if cycle.action_plan is not None:
        committed = cycle.action_plan.steps[cycle.action_plan.committed_step_index]
        action_type = committed.action_type
    verdict = None
    if cycle.falsification is not None:
        verdict = cycle.falsification.verdict.value

    return CycleResponse(
        cycle_id=str(cycle.cycle_id),
        correlation_id=cycle.correlation_id,
        committed=cycle.committed,
        execution_verified=cycle.execution_verified,
        proposal_status=_proposal_status(cycle),
        decision_package_digest=cycle.decision_package_digest,
        action_type=action_type,
        falsification_verdict=verdict,
    )


class ClassificationCycleRequest(BaseModel):
    classifications: list[dict]
    additional_signals: list[dict] = []


@router.post("/classify-and-run", response_model=CycleResponse)
async def classify_and_run(request: ClassificationCycleRequest) -> CycleResponse:
    """Accept deepfield-fleet ClassificationRecords, convert to Evidence, run a cycle."""
    evidence = batch_classifications_to_evidence(request.classifications)

    for sig in request.additional_signals:
        evidence.append(Evidence(
            metric=sig.get("metric", "unknown"),
            value=float(sig.get("value", 0)),
            source=sig.get("source", "external"),
        ))

    if not evidence:
        raise HTTPException(status_code=400, detail="No evidence produced from classifications.")

    cycle = await _driver.run_cycle(evidence)
    _cycles[str(cycle.cycle_id)] = cycle

    action_type = None
    if cycle.action_plan is not None:
        committed = cycle.action_plan.steps[cycle.action_plan.committed_step_index]
        action_type = committed.action_type

    verdict = None
    if cycle.falsification is not None:
        verdict = cycle.falsification.verdict.value

    return CycleResponse(
        cycle_id=str(cycle.cycle_id),
        correlation_id=cycle.correlation_id,
        committed=cycle.committed,
        execution_verified=cycle.execution_verified,
        proposal_status=_proposal_status(cycle),
        decision_package_digest=cycle.decision_package_digest,
        action_type=action_type,
        falsification_verdict=verdict,
    )
