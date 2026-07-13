# Governed Cognitive Loop

The governed decision-synthesis layer for AI inference fleet management. It turns observations and forecasts into strict, signed, expiry-bounded `DecisionPackage` proposals. GCL does not authorize or execute infrastructure changes.

## Platform boundary

```text
rev_deepfield -> GCL -> agent-promotion -> governance-strata -> ARE -> fleet-llm-d
 observations    signed       proposer          transaction      grant    actuation
 and forecasts   package      ceiling           lifecycle        receipt
```

| System | Owns | Does not own |
|---|---|---|
| `rev_deepfield` | Observations, findings, forecasts | Decisions, actuation |
| GCL | Decision synthesis, alternatives, falsification, signed package | Authorization, actuation |
| agent-promotion | Proposer autonomy ceiling | Final execution authorization |
| governance-strata | Transaction lifecycle | Infrastructure actuation |
| ARE | Execution authorization, grants, immutable receipt truth | Decision synthesis, actuation |
| fleet-llm-d | Authorized fleet desired, observed, and operation state | Forecasting, final authorization |

## Decision cycle

Every governed cycle follows this chain:

1. Classify constraints from evidence, deterministic rules first and an LLM only for ambiguity.
2. Predict a trajectory over the planning horizon.
3. Interpret an objective. The LLM can set the goal but never the action.
4. Compute candidate actions under hard constraints with the deterministic controller.
5. Falsify the selected candidate with disconfirmation checks.
6. Build and sign a `DecisionPackage` with candidates, rejected alternatives, authority, evidence digests, confidence, and expiry.
7. Publish the package as a structured CloudEvents 1.0 proposal.

The `LoopCycle.committed` field means that a decision package was committed after falsification. It does not mean infrastructure execution. Proposal acknowledgements always report `execution_verified=false`.

## Action candidates

| Action | Example trigger | DecisionPackage action class |
|---|---|---|
| `no_action` | Stable system | Internal only, no package emitted |
| `scale` | Latency breach with capacity | `fleet.scale` |
| `pre_warm` | Approaching an SLO threshold | `fleet.prewarm` |
| `shed_load` | Exhausted capacity and latency breach | `fleet.shed_load` |
| `alert` | Compliance constraint without an actionable target | Rejected from the fleet proposal contract |
| `migrate` | Compliance and capacity exhaustion | `fleet.migrate` |
| `rollback` | Legacy recovery candidate | Rejected; governance-strata owns compensation |

Only the canonical ARE fleet action classes are accepted in a `DecisionPackage`: `fleet.deploy`, `fleet.scale`, `fleet.route`, `fleet.prewarm`, `fleet.shed_load`, `fleet.migrate`, and `fleet.kv_transfer`.

## Security modes

Production is fail closed. Missing or unreachable passport and authority dependencies deny package creation. Production requires explicit decision-signing key material.

Standalone tests must deliberately opt in:

```bash
GCL_RUNTIME_MODE=standalone-test
```

Only that mode permits labeled test-only authority bypass and the deterministic test signing key. Legacy fleet v1 HMAC submission is always disabled in production and requires both of these development settings:

```bash
GCL_RUNTIME_MODE=development
GCL_ALLOW_LEGACY_FLEET_HMAC_DEVELOPMENT_COMPAT=true
```

The legacy response is transport acknowledgement only and never verified execution.

## Current evidence level

The repository has executable unit, property, scenario, DecisionPackage, CloudEvent, proposer transport, and fail-closed security tests. Those tests are contract and component evidence. They are not live fleet execution, external ARE receipt, multi-cluster OpenShift, performance, chaos, soak, security-audit, Blue, or Gold evidence.

Historical benchmark documents remain useful test-design context. Their environment-specific observations are not current promotion evidence without a reproducible external evidence bundle.

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

The proposer endpoint is:

```text
POST {GCL_PROPOSER_URL}/api/v1/proposals/decision-packages
Content-Type: application/cloudevents+json
```

## Documentation

- [DecisionPackage v1](docs/decision-package-v1.md)
- [Architecture](docs/architecture.md)
- [Data contracts](docs/contracts.md)
- [Event flow and evidence boundary](docs/event-flow-proof.md)
- [White paper](docs/whitepaper/governed-cognitive-loop-whitepaper.md)
- [Historical benchmark context](docs/benchmarks/gcl-benchmarks.md)
