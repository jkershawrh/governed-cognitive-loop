# Architecture

## Platform Overview

GCL is one decision producer in the wider governed inference fleet platform:

```
deepfield-fleet -> GCL -> fleet-llm-d
 observations      signed      admission, authorization, operation, actuation
 and forecasts     advisory package
                         \
                          -> are-immutable-ledger (evidence/proof only)
```

## GCL Components

| Component | Responsibility | LLM involvement |
|---|---|---|
| ConstraintClassifier | Evidence to typed constraints (two-stage: deterministic first, LLM for ambiguous) | Second stage only |
| HorizonPredictor | Current state to trajectory (linear regression + spike detection) | None |
| ObjectiveInterpreter | Context to ObjectiveSpec (cost terms, weights, rationale) | Primary (with template fallback) |
| Controller | Trajectory + objective + constraints to ActionPlan (numpy, deterministic) | None |
| FalsificationGate | Pre-commit disconfirmation (7 checks + optional LLM adversary) | Optional probe |
| Committer | Commit a signed decision package, propose or reject, record the decision | None |
| LoopDriver | Orchestrates the full cycle, advances receding horizon | None |

Supporting adapters:
| Adapter | Purpose |
|---|---|
| ClassificationAdapter | Transforms deepfield-fleet ClassificationRecords to Evidence |
| DeepFieldEventAdapter | Consumes pinned DeepField-owned CloudEvents and preserves producer provenance |
| FleetIntentAdapter (`ProposerAdapter` compatibility alias) | Publishes signed DecisionPackage CloudEvents to fleet-llm-d intent admission |
| FleetAdapter | Disabled production compatibility adapter for legacy v1 HMAC submission |
| IntentMapping | ScaleIntent, PreWarmIntent, ShedLoadIntent, AlertIntent, MigrateIntent |

## The Honesty Boundary

The LLM interprets context into an objective and predicts disturbances. That is all.

The LLM never computes the committed control action and never performs constraint satisfaction. A deterministic controller owns optimization and the hard-constraint guarantee. A test proves this by AST inspection: the interpreter module has no import of ActionPlan or ActionStep.

This system does not claim optimality. The objective is LLM-specified, so classical optimality guarantees do not hold. The guarantee is: hard-constraint satisfaction and falsification-gated commit.

## Decision Flow

```
DeepField CloudEvent arrives at /api/v1/events/deepfield
      |
[1] gcl.classify ---- constraints derived from evidence
[2] gcl.predict ----- trajectory forecast over horizon
[3] gcl.interpret --- objective set (LLM or template, never an action)
[4] gcl.plan -------- action computed under hard constraints
[5] gcl.falsify ----- plan challenged (7 deterministic checks)
[6] sign package ---- survived, expiry-bounded decision package
    gcl.reject ------ failed, held with reason
      |
[7] gcl.decision_package.proposed (execution_verified=false)
      |
[8] CloudEvent 1.0 to fleet-llm-d /api/v2/intents
[9] fleet-llm-d admits, authorizes, and progresses FleetIntent/FleetOperation
      |
[10] fleet-llm-d reconciles an authorized operation
[11] components record evidence receipts in are-immutable-ledger
```

## Receding Horizon

The controller computes candidates over the full horizon but selects only the first step (`committed_step_index` is enforced to 0 by a Pydantic validator). Committing that decision means signing and proposing a package. It does not mean infrastructure execution.

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

GCL can consume multi-cluster observations. Mock cluster state is test input only and is not live ModelPlane evidence. Evidence labels can identify a cluster so a decision package preserves its source scope.

When compliance and capacity exhaustion occur together, the controller can propose a `migrate` candidate. Only an authorized fleet operation can trigger relocation.

## Ledger Chain

Each cycle writes correlated decision evidence through the configured `are-immutable-ledger` client. The client uses `POST /api/receipts`, queries `GET /api/receipts/chain`, and can verify with `GET /api/receipts/verify`. Receipts prove recorded evidence; they never authorize fleet execution. In-memory test entries are explicitly local-only evidence.

See [DecisionPackage v1](decision-package-v1.md) for the exact producer contract and security modes.
