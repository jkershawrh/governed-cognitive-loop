# Architecture

## Platform Overview

Four systems compose the governed inference fleet platform:

```
deepfield-fleet              governed-cognitive-loop         fleet-llm-d              ARE Immutable Ledger
(predictive brain)           (governed autonomy)             (fleet controller)       (audit backbone)

Observes + classifies        Derives constraints             Evaluates policy         Stores every
evidence from metrics,       Predicts trajectory             Accepts/refuses          decision as
logs, images, events.        Interprets objective            intents. Assigns         hash-chained
Produces Classification      Optimizes under constraints     placement. Routes        entries under
Records.                     Falsifies before commit         traffic. Records         correlation IDs.
                             Commits or rejects              decisions.               Verifies chains.
```

## GCL Components

| Component | Responsibility | LLM involvement |
|---|---|---|
| ConstraintClassifier | Evidence to typed constraints (two-stage: deterministic first, LLM for ambiguous) | Second stage only |
| HorizonPredictor | Current state to trajectory (linear regression + spike detection) | None |
| ObjectiveInterpreter | Context to ObjectiveSpec (cost terms, weights, rationale) | Primary (with template fallback) |
| Controller | Trajectory + objective + constraints to ActionPlan (numpy, deterministic) | None |
| FalsificationGate | Pre-commit disconfirmation (7 checks + optional LLM adversary) | Optional probe |
| Committer | Actuate or reject, record to ledger | None |
| LoopDriver | Orchestrates the full cycle, advances receding horizon | None |

Supporting adapters:
| Adapter | Purpose |
|---|---|
| ClassificationAdapter | Transforms deepfield-fleet ClassificationRecords to Evidence |
| FleetAdapter | Maps committed actions to fleet-llm-d intents (HMAC-SHA256 auth) |
| IntentMapping | ScaleIntent, PreWarmIntent, ShedLoadIntent, AlertIntent, MigrateIntent |

## The Honesty Boundary

The LLM interprets context into an objective and predicts disturbances. That is all.

The LLM never computes the committed control action and never performs constraint satisfaction. A deterministic controller owns optimization and the hard-constraint guarantee. A test proves this by AST inspection: the interpreter module has no import of ActionPlan or ActionStep.

This system does not claim optimality. The objective is LLM-specified, so classical optimality guarantees do not hold. The guarantee is: hard-constraint satisfaction and falsification-gated commit.

## Decision Flow

```
Evidence arrives (Prometheus, Kubernetes, classification)
      |
[1] gcl.classify ---- constraints derived from evidence
[2] gcl.predict ----- trajectory forecast over horizon
[3] gcl.interpret --- objective set (LLM or template, never an action)
[4] gcl.plan -------- action computed under hard constraints
[5] gcl.falsify ----- plan challenged (7 deterministic checks)
[6] gcl.commit ------ survived, committed
    gcl.reject ------ failed, held with reason
      |
[7] POST /api/v1/intents (HMAC-SHA256 auth)
      |
[8] fleet-llm-d evaluates against policy
[9] fleet.placement.assigned / fleet.model.deployed / fleet.routing.shifted
      |
[10] ARE Ledger: all entries hash-chained per type, correlation-linked per cycle
```

## Receding Horizon

The controller computes actions over the full horizon but marks only the first step as committed (committed_step_index is enforced to 0 by a Pydantic validator). After committing (or rejecting), the loop re-measures and re-plans from fresh data.

## Falsification Checks

7 deterministic checks run in order before an optional LLM adversarial probe:

1. **capacity_available**: replicas exceed capacity bound or max_replicas evidence
2. **scale_magnitude_reasonable**: replicas exceed config max_scale_replicas (default 20)
3. **warmup_time_realistic**: assumed warmup faster than measured (with 1.5x safety multiplier)
4. **prediction_confidence**: trajectory confidence below floor (default 0.5)
5. **compliance_action_valid**: compliance constraint active but action is scale/pre_warm
6. **shed_load_bounded**: duration outside 1-3600s or max_inflight <= 0
7. **migration_target_available**: migrate action without a target pool

## Multi-Cluster and ModelPlane

The GCL integrates with fleet-llm-d's ModelPlane system for multi-cluster awareness. The ModelPlane mock provides cluster state (edge-east, edge-west, sovereign-eu, dev-cluster-1-cpu). Evidence carries cluster labels (`labels={"cluster": "edge-east"}`) so ledger entries trace which cluster each decision targets.

When compliance + capacity exhaustion occur together, the controller produces a `migrate` action instead of just an `alert`, triggering cross-cluster workload relocation.

## Ledger Chain

Each cycle writes a chain under one correlation ID: classified constraints, predicted trajectory, interpreted objective, proposed action, falsification result, and commit/reject outcome. Every entry is hash-chained (SHA-256) per entry type and can be verified via `GET /api/verify`.
