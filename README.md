# Governed Cognitive Loop

Governed Cognitive Loop (GCL) is a proposal-only governance kernel for systems that make consequential operational decisions from machine-generated evidence.

GCL turns observations, evaluations, and forecasts into constrained, falsified, signed, and expiry-bounded `DecisionPackage` proposals. It never grants execution authority and never treats a delivery acknowledgement as proof that an action occurred.

The current `0.1` implementation is proven in an AI inference-fleet use case. The [OSS architecture](docs/oss-architecture.md) defines the portable core and adapter model for TrustyAI, EvalHub, Prometheus, OpenTelemetry, OPA, CloudEvents, proof stores, human workflows, and other proposal consumers.

## The boundary

```text
evidence producers              GCL                    external authorities

TrustyAI / EvalHub  ─┐    validate and normalize       human approval
Prometheus / OTEL    ├──> constrain and forecast   ───> policy admission
CloudEvents          │    generate alternatives         workflow engines
domain systems       ┘    falsify, sign, expire         control planes
                                  |
                                  v
                         proof and telemetry sinks
```

GCL owns decision synthesis, alternatives, falsification, provenance, and the signed proposal. External systems retain ownership of measurements, authorization, actuation, rollback, and observed outcomes.

## Why GCL

Responsible-AI and observability tools can tell you that a model is drifting, an evaluation failed, or an SLO is at risk. Control planes and workflow engines can execute changes. GCL fills the governed decision gap between those systems:

- machine evidence is scoped, freshness-checked, and traceable;
- an optional LLM may frame the objective, but cannot choose the action;
- deterministic code computes candidates and enforces hard constraints;
- the selected candidate must survive explicit disconfirmation checks;
- rejected alternatives remain in the decision record;
- the proposal is signed, scope-bound, and expires;
- a separate authority accepts or rejects it.

GCL does not claim optimality. Its guarantee is narrower: deterministic hard-constraint handling and falsification-gated proposal commit.

## Decision cycle

1. Validate and normalize evidence.
2. Classify hard and soft constraints.
3. Predict a bounded trajectory.
4. Interpret the objective with a deterministic fallback.
5. Compute candidate actions under hard constraints.
6. Falsify the selected candidate.
7. Build and sign a `DecisionPackage` with alternatives and evidence references.
8. Offer the package to an external proposal consumer.
9. Correlate independently observed outcomes later.

`LoopCycle.committed` currently means the signed proposal survived falsification and was committed to the proposal path. It does not mean authorized or executed. Proposal responses always set `execution_verified=false`.

## Current and planned integrations

| Integration | Role | Status |
|---|---|---|
| DeepField CloudEvents | Evidence source | Implemented reference adapter |
| fleet-llm-d | Signed proposal consumer | Implemented reference adapter |
| are-immutable-ledger | Evidence and proof receipts | Implemented optional adapter |
| OpenAI-compatible inference | Optional objective interpretation and adversarial probe | Implemented with deterministic fallbacks |
| OPA | LLM honesty-boundary policy | Implemented deployment example |
| TrustyAI Service | Drift and fairness evidence | Planned first OSS integration |
| EvalHub | Evaluation and collection-compliance evidence | Planned first OSS integration |
| Prometheus and Alertmanager | Metric and alert evidence | Planned |
| OpenTelemetry | Cross-system correlation and telemetry | Planned |
| Generic CloudEvents and webhooks | Portable evidence and proposal transport | Planned |

See [ROADMAP.md](ROADMAP.md) for release order. Planned items are not implemented claims.

## Run locally

Python 3.9 or later is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
GCL_RUNTIME_MODE=standalone-test \
GCL_FORCE_DETERMINISTIC=1 \
uvicorn gcl.api.app:create_app --factory --port 8000
```

In another terminal, run a deterministic scenario:

```bash
curl -X POST http://localhost:8000/api/v1/scenario/seed \
  -H 'Content-Type: application/json' \
  -d '{"scenario":"inference_fleet_spike","seed":42}'
```

The standalone-test mode uses local-only defaults and must not be used in production.

## Develop and verify

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
GCL_RUNTIME_MODE=standalone-test \
GCL_FORCE_DETERMINISTIC=1 \
python -m pytest -q
```

Exported schemas:

```text
GET /api/v1/contracts/decision-package-v1/schema
GET /api/v1/contracts/decision-package-cloudevent-v1/schema
```

## Production safety

Production requires external Ed25519 signing material, authenticated evidence ingestion, workload identity for proposal delivery, and an independent authorizer at the consumer.

The deterministic test signer is available only in standalone-test mode. Legacy fleet HMAC submission is disabled in production. Local in-memory proof records are development evidence, not immutable receipts.

Read [SECURITY.md](SECURITY.md) before deploying GCL.

## Project status

GCL is pre-1.0 and its portable adapter model is under active design. DecisionPackage v1, component tests, property tests, scenarios, security-boundary tests, and a live single-cluster ecosystem stress run exist today. These do not establish multi-cluster production readiness, a completed independent security audit, or TrustyAI interoperability.

The project is intentionally preserving the working fleet reference implementation while extracting a standalone governance kernel incrementally. The target architecture is documented before the breaking refactor so integrations can converge on stable ports instead of private implementation details.

## Documentation

- [OSS architecture and integration model](docs/oss-architecture.md)
- [Roadmap](ROADMAP.md)
- [DecisionPackage v1](docs/decision-package-v1.md)
- [Current implementation architecture](docs/architecture.md)
- [Data contracts](docs/contracts.md)
- [Event flow and evidence boundary](docs/event-flow-proof.md)
- [Governance](GOVERNANCE.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [White paper](docs/whitepaper/governed-cognitive-loop-whitepaper.md)

## License

Licensed under the [Apache License 2.0](LICENSE).
