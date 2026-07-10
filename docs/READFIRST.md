# READFIRST: Findings and Assumptions

## deepfield-fleet

Sibling project providing fleet management with microagents, intents, and macroagents.

Key components to interface with:
- `app/microagents/slo_forecaster.py`: Linear regression on latency metrics with R-squared confidence. Reuse the algorithm pattern for HorizonPredictor.
- `app/domain/fleet_intents.py`: `PreWarmIntent`, `ScaleIntent`, `ShedLoadIntent` inherit from `FleetIntent`. The FleetAdapter must produce structurally compatible intents.
- `app/intents/emitter.py`: Sends intents to fleet-llm-d at `/api/v1/intents` via httpx.
- `app/macroagents/consequence_scoper.py`: Reference for how scoping and evidence evaluation work.
- `app/inference/client.py`: `infer()` returns `Optional[InferenceResult]`, returns `None` when unconfigured. `set_force_rules(True)` globally disables LLM. Replicate this pattern.

## are-immutable-ledger

Immutable audit ledger service (gRPC with REST gateway).

REST API contract:
- `POST /api/entries` with `{entry_type, agent_id, content, content_type, source_id, correlation_id}`, returns `{entry_id, entry_hash, chain_position, written_ts}`
- `GET /api/receipts/chain?correlation_id=X` for trust chain queries

## Integration strategy

This project has zero import-time dependencies on either sibling. Communication is over HTTP. Local copies of compatible Pydantic models are maintained. In-memory fallbacks when services are unavailable.

## Assumptions

1. LLM endpoint follows OpenAI-compatible chat completions API.
2. Ledger REST gateway is at the URL configured in `GCL_LEDGER_URL`.
3. Fleet endpoint is at the URL configured in `GCL_FLEET_URL`.
4. All three external services are optional at development time (skip flags and fallbacks).
