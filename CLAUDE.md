# governed-cognitive-loop

The governed autonomy layer for AI inference fleet management. Sits between deepfield-fleet (prediction) and fleet-llm-d (actuation).

## Build and run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Test

```bash
python3 -m pytest tests/ -q                    # 776 tests
python3 -m pytest tests/test_rubrics.py -v     # 24/24 EDD rubric
```

## Verify (full suite)

```bash
GCL_FORCE_DETERMINISTIC=1 GCL_LEDGER_SKIP=1 bash verify.sh
```

## Run locally

```bash
# Backend only
uvicorn gcl.api.app:create_app --factory --port 8000

# Frontend dev server (proxies /api to :8000)
cd frontend && npm run dev

# Full stack with ledger (podman)
python3 -m podman_compose up -d
```

## Run scenarios

```bash
# Seed and run
curl -X POST http://localhost:8000/api/v1/scenario/seed \
  -H 'Content-Type: application/json' \
  -d '{"scenario": "inference_fleet_spike", "seed": 42}'

# Available scenarios: inference_fleet_spike, compliance_breach,
# capacity_exhaustion, slo_cascade, mixed_storm, multi_cluster_migration
```

## Deploy to OpenShift (Oberon)

```bash
# Build and push
podman build --platform linux/amd64 -t quay.io/rh-ee-jkershaw/gcl-demo:latest -f Containerfile .
podman push quay.io/rh-ee-jkershaw/gcl-demo:latest

# Deploy
export KUBECONFIG=/tmp/oberon.kubeconfig
oc apply -f deploy/namespace.yaml
oc apply -f deploy/deployment.yaml
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| GCL_FORCE_DETERMINISTIC | false | Skip all LLM calls, use deterministic fallbacks |
| GCL_LEDGER_URL | (empty) | ARE ledger REST gateway URL |
| GCL_FLEET_URL | (empty) | fleet-llm-d controller URL |
| GCL_FLEET_TOKEN | (empty) | Shared secret for HMAC-SHA256 fleet auth |
| GCL_LEDGER_SKIP | (unset) | Skip ledger reachability in preflight |
| GCL_MAX_SCALE_REPLICAS | 20 | Upper bound on any single scale action |
| GCL_SPIKE_DETECTION_THRESHOLD | 2.0 | Peak-to-baseline ratio for spike detection |

## Conventions

- No em-dashes anywhere (use commas, colons, periods, parentheses)
- CDD contracts first, then TDD, then BDD, then EDD rubric, then CBT
- The LLM never computes the committed action. A deterministic controller owns optimization.
- Do not claim optimality. The guarantee is hard-constraint satisfaction and falsification-gated commit.
- Every LLM call site must have a deterministic fallback.

## Architecture

See `docs/architecture.md` for the full 4-system platform architecture.
See `docs/event-flow-proof.md` for the decision chain proof map.
See `docs/whitepaper/governed-cognitive-loop-whitepaper.md` for the white paper.
See `docs/benchmarks/gcl-benchmarks.md` for verified results.
