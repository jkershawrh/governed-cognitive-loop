# Governed Cognitive Loop

The governed autonomy layer for AI inference fleet management. It sits between prediction (deepfield-fleet) and actuation (fleet-llm-d), ensuring every infrastructure decision is constrained, challenged, and recorded before it executes.

## Platform Architecture

```
deepfield-fleet ──classifications──> GCL ──intents──> fleet-llm-d
  (predictive brain)             (governed       (fleet controller)
                                  autonomy)  |
                                             └──every decision──> ARE Immutable Ledger
                                                                   (audit backbone)
```

| System | Owns | Does not own |
|---|---|---|
| **deepfield-fleet** | Observation, classification, prediction | Decisions, actuation |
| **governed-cognitive-loop** | Constraint derivation, optimization, falsification, commit/reject | Raw observation, actuation |
| **fleet-llm-d** | Policy enforcement, actuation, cluster management | Classification, planning |
| **ARE Immutable Ledger** | Hash-chained audit trail, chain verification | Any decisions |

## What It Does

Every governed cycle follows this chain:

1. **Classify** constraints from evidence (deterministic rules first, LLM for ambiguous)
2. **Predict** a trajectory over the planning horizon (linear regression + spike detection)
3. **Interpret** an objective (LLM or template sets the goal, never the action)
4. **Optimize** an action plan under hard constraints (numpy, deterministic)
5. **Falsify** the committed step (7 disconfirmation checks try to break the plan)
6. **Commit** only what survives (or reject with the reason named)
7. **Record** the full decision chain to the ARE ledger under one correlation ID

## The Honesty Boundary

- The LLM interprets context into an objective and predicts disturbances. That is all.
- The LLM never computes the committed action and never performs constraint satisfaction. A deterministic controller owns optimization.
- This system does not claim optimality. The guarantee is: hard-constraint satisfaction and falsification-gated commit.
- Falsification seeks disconfirmation. It tries to break the plan, not confirm it.

## Action Types

| Action | When | Intent sent to |
|---|---|---|
| `no_action` | System stable, no intervention needed | (none) |
| `scale` | Latency breach, capacity available | fleet-llm-d ScaleIntent |
| `pre_warm` | Approaching SLO threshold | fleet-llm-d PreWarmIntent |
| `shed_load` | Capacity exhausted, latency breached | fleet-llm-d ShedLoadIntent |
| `alert` | Compliance constraint active | fleet-llm-d AlertIntent |
| `migrate` | Compliance + capacity exhaustion (cross-cluster) | fleet-llm-d MigrateIntent |

## Verified Results

| Metric | Value |
|---|---|
| Tests | 496 (unit + property + BDD + EDD) |
| EDD rubric dimensions | 15/15 green |
| Scenarios | 6 (inference spike, compliance, capacity exhaustion, SLO cascade, mixed storm, multi-cluster) |
| Edge case simulations | 24/24 pass, 0 crashes, 4/4 behavioral correctness |
| Ledger entries (Oberon) | 1,098 GCL entries, all chains cryptographically valid |
| Governed cycles | 129+ (96 committed, 33 rejected with named reasons) |
| Composite confidence | 85% for CPU inference scaling |

See [benchmarks](docs/benchmarks/gcl-benchmarks.md) and [white paper](docs/whitepaper/governed-cognitive-loop-whitepaper.md) for details.

## Quick Start

### Local development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
GCL_FORCE_DETERMINISTIC=1 GCL_LEDGER_SKIP=1 bash verify.sh
```

### Podman (full stack with ledger)

```bash
python3 -m podman_compose up -d
# GCL app: http://localhost:8000
# Includes: postgres, ARE ledger, REST gateway, GCL app + frontend
```

### OpenShift (Oberon)

```bash
oc apply -f deploy/namespace.yaml
oc apply -f deploy/deployment.yaml
# Connects to fleet-llm-d and ARE ledger in adjacent namespaces
```

### Run a scenario

```bash
curl -X POST http://localhost:8000/api/v1/scenario/seed \
  -H 'Content-Type: application/json' \
  -d '{"scenario": "inference_fleet_spike", "seed": 42}'

# Step through 8 cycle steps
for i in $(seq 0 7); do
  signals=$(curl -s http://localhost:8000/api/v1/scenario/step/$i | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)['signals']))")
  curl -X POST http://localhost:8000/api/v1/cycle \
    -H 'Content-Type: application/json' -d "{\"signals\": $signals}"
done
```

### Send classifications from deepfield-fleet

```bash
curl -X POST http://localhost:8000/api/v1/classify-and-run \
  -H 'Content-Type: application/json' \
  -d '{
    "classifications": [{
      "class_name": "slo_breach_predicted",
      "severity": "critical",
      "confidence": 0.92,
      "metrics": {"forecast_value": 6200}
    }],
    "additional_signals": [
      {"metric": "replicas", "value": 3},
      {"metric": "max_replicas", "value": 10}
    ]
  }'
```

## Frontend Demo

The React frontend (built with the deepfield-multimodal visual system) provides a navigable story-arc demo with 4 layers:

- **Layer 0 (Hook):** Falsification gate rejects a bad action
- **Layer 1 (Evidence):** Constraints derived from evidence, not stale rules
- **Layer 2 (Lookahead):** Horizon plot with trajectory, constraints, committed step
- **Layer 3 (Floor):** LLM/Controller honesty boundary and ledger chain

Start the backend and open `http://localhost:8000`. Press Enter to begin.

## Documentation

- [White Paper](docs/whitepaper/governed-cognitive-loop-whitepaper.md)
- [Benchmarks](docs/benchmarks/gcl-benchmarks.md)
- [Event Flow Proof](docs/event-flow-proof.md)
- [Architecture](docs/architecture.md)
- [Story Arc](docs/story-arc.md)
- [SA Walkthrough](docs/walkthrough.md)
- [Beat-to-Cycle Mapping](docs/MAPPING.md)
- [Data Contracts](docs/contracts.md)
