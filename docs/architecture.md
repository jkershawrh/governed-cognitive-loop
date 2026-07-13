# Architecture

## Platform Overview

GCL is one decision producer in the wider governed inference fleet platform:

```
rev_deepfield -> GCL -> agent-promotion -> governance-strata -> ARE -> fleet-llm-d
 observations    signed       proposer          transaction      grant    actuation
 and forecasts   package      ceiling           lifecycle        receipt
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
| ProposerAdapter | Publishes signed DecisionPackage CloudEvents to proposer authority |
| FleetAdapter | Disabled production compatibility adapter for legacy v1 HMAC submission |
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
[6] sign package ---- survived, expiry-bounded decision package
    gcl.reject ------ failed, held with reason
      |
[7] gcl.decision_package.proposed (execution_verified=false)
      |
[8] CloudEvent 1.0 to proposer authority
[9] governance-strata and ARE may authorize a FleetIntent/FleetOperation
      |
[10] fleet-llm-d may reconcile an authorized operation
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

Each cycle writes correlated decision entries through the configured ledger client. The signed package carries content and evidence digests. ARE remains the authority for immutable receipt-chain truth. In-memory test ledger entries are not external ARE evidence.

See [DecisionPackage v1](decision-package-v1.md) for the exact producer contract and security modes.
