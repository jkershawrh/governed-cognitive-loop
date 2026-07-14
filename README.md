# Governed Cognitive Loop

The governed decision-synthesis layer for AI inference fleet management. It turns observations and forecasts into strict, signed, expiry-bounded `DecisionPackage` proposals. GCL does not authorize or execute infrastructure changes.

## Platform boundary

```text
deepfield-fleet -> GCL -> fleet-llm-d
 observations      signed      admission, authorization, operations, actuation
 and forecasts     advisory DecisionPackage
                         \
                          -> are-immutable-ledger (evidence and proof only)
```

| System | Owns | Does not own |
|---|---|---|
| `deepfield-fleet` | Observations, findings, forecasts | Decisions, authorization, actuation |
| GCL | Decision synthesis, alternatives, falsification, signed package | Authorization, actuation |
| `fleet-llm-d` | Intent admission, authorization, desired/observed/operation state, actuation | Forecasting, decision synthesis |
| [`are-immutable-ledger`](https://github.com/jkershawrh/are-immutable-ledger) | Immutable evidence receipts and proof verification | Authorization, admission, actuation |
| agent-promotion (optional) | Non-authoritative proposer-ceiling provenance | Fleet admission or execution authorization |

## Decision cycle

Every governed cycle follows this chain:

1. Classify constraints from evidence, deterministic rules first and an LLM only for ambiguity.
2. Predict a trajectory over the planning horizon.
3. Interpret an objective. The LLM can set the goal but never the action.
4. Compute candidate actions under hard constraints with the deterministic controller.
5. Falsify the selected candidate with disconfirmation checks.
6. Build and sign an advisory `DecisionPackage` with candidates, rejected alternatives, evidence digests, confidence, and expiry.
7. Submit the package as a structured CloudEvents 1.0 event to fleet-llm-d's `/api/v2/intents` boundary.

The `LoopCycle.committed` field means that a decision package was committed after falsification. It does not mean infrastructure execution. Proposal acknowledgements always report `execution_verified=false`.

The canonical input boundary is:

```text
POST /api/v1/events/deepfield
Content-Type: application/cloudevents+json
```

It consumes DeepField-owned observation, finding, forecast, and advisory
remediation CloudEvents v1. GCL pins their event/schema identities without
claiming ownership of their payload contracts. Expired or mismatched events
are rejected; correlation, causation, idempotency, and evidence digests flow
into the resulting DecisionPackage.

Production requires the configured DeepField source and
`GCL_DEEPFIELD_EVENT_BEARER_TOKEN`. Manual `/cycle`, direct fleet-metrics, and
legacy `/classify-and-run` ingestion are development/test compatibility paths
and return `403` in production.

## Action candidates

| Action | Example trigger | DecisionPackage action class |
|---|---|---|
| `no_action` | Stable system | Internal only, no package emitted |
| `scale` | Latency breach with capacity | `fleet.scale` |
| `pre_warm` | Approaching an SLO threshold | `fleet.prewarm` |
| `shed_load` | Exhausted capacity and latency breach | `fleet.shed_load` |
| `alert` | Compliance constraint without an actionable target | Rejected from the fleet proposal contract |
| `migrate` | Compliance and capacity exhaustion | `fleet.migrate` |
| `rollback` | Legacy recovery candidate | Rejected; fleet-llm-d owns operation compensation |

Only canonical fleet action classes are accepted in a `DecisionPackage`: `fleet.deploy`, `fleet.scale`, `fleet.route`, `fleet.prewarm`, `fleet.shed_load`, `fleet.migrate`, and `fleet.kv_transfer`.

## Security modes

Production requires explicit decision-signing key material and an OIDC credential for fleet submission. GCL does not call an external authorization service: fleet-llm-d authenticates the caller, validates the signed advisory package, authorizes any resulting operation, and owns actuation.

Standalone tests must deliberately opt in:

```bash
GCL_RUNTIME_MODE=standalone-test
```

Only that mode permits the deterministic test signing key. Legacy fleet v1 HMAC submission is always disabled in production and requires both of these development settings:

```bash
GCL_RUNTIME_MODE=development
GCL_ALLOW_LEGACY_FLEET_HMAC_DEVELOPMENT_COMPAT=true
```

The legacy response is transport acknowledgement only and never verified execution.

## Current evidence level

The repository has executable unit, property, scenario, DecisionPackage, CloudEvent, fleet transport, and security-boundary tests (822 passing). An 8-phase ecosystem stress test exercised the full 4-system platform on the Oberon cluster: 42/48 passed, including pressure testing at 50 concurrent governance cycles (0 errors), a 300-cycle soak (0 errors, 1.2x latency drift), degradation testing across all 6 scenarios, and pen testing with 0 vulnerabilities found.

These tests are contract, component, and live Oberon evidence. They are not multi-cluster OpenShift, 72-hour soak, security-audit, Blue, or Gold evidence.

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
GCL_RUNTIME_MODE=standalone-test GCL_FORCE_DETERMINISTIC=1 python -m pytest -q
```

Run the API locally:

```bash
GCL_RUNTIME_MODE=standalone-test uvicorn gcl.api.app:create_app --factory --port 8000
```

Schema exports:

```text
GET /api/v1/contracts/decision-package-v1/schema
GET /api/v1/contracts/decision-package-cloudevent-v1/schema
```

The fleet intent endpoint is:

```text
POST {GCL_FLEET_INTENTS_URL}/api/v2/intents
Content-Type: application/cloudevents+json
```

`GCL_AGENT_PROMOTION_URL` is optional compatibility metadata. If configured,
its attestation is embedded as `non_authoritative=true`; allow, refuse, and
unavailable results never decide whether GCL submits the package.

## Documentation

- [DecisionPackage v1](docs/decision-package-v1.md)
- [Architecture](docs/architecture.md)
- [Data contracts](docs/contracts.md)
- [Event flow and evidence boundary](docs/event-flow-proof.md)
- [White paper](docs/whitepaper/governed-cognitive-loop-whitepaper.md)
- [Historical benchmark context](docs/benchmarks/gcl-benchmarks.md)
- [Ecosystem stress test benchmarks](docs/benchmarks/ecosystem-stress-benchmarks.md)
