# Event Flow Proof: Platform Decision Chain

Every decision in this platform is recorded as a hash-chained entry in the ARE Immutable Ledger. This document maps the complete decision flow across the four systems and shows the proof.

## The Four Systems

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

## Decision Flow (one governed cycle)

```
deepfield-fleet
  ClassificationRecord (e.g. slo_breach_predicted, confidence=0.92)
      |
      | POST /api/v1/classify-and-run
      v
governed-cognitive-loop
  [1] gcl.classify ---- derive constraints from evidence
  [2] gcl.predict ----- forecast trajectory (linear regression + spike detection)
  [3] gcl.interpret --- set objective (template or LLM, never an action)
  [4] gcl.plan -------- compute action under hard constraints (numpy)
  [5] gcl.falsify ----- challenge the plan (capacity? warmup? confidence? compliance?)
  [6] gcl.commit ------ plan survived, commit
      gcl.reject ------ plan failed, hold (one of these, never both)
      |
      | if committed: POST /api/v1/intents (HMAC-SHA256 signed token)
      v
fleet-llm-d
  [7] intent evaluated against policy (confidence >= 0.5, replicas <= max)
  [8] fleet.placement.assigned -- cluster selected by constraint solver
  [9] fleet.model.deployed ---- deployment created or scaled
  [10] fleet.routing.shifted --- traffic weight updated
      |
      v
ARE Immutable Ledger
  All entries hash-chained (SHA-256) per entry_type
  All entries correlation-linked per cycle
  GET /api/verify confirms every chain is intact
```

## Ledger Entry Types

### GCL entries (source: gcl)

| Entry Type | Written When | Content | Proves |
|---|---|---|---|
| gcl.classify | Every cycle | List of constraints with evidence IDs | Constraints derived from evidence, not stale rules |
| gcl.predict | Every cycle | Trajectory points, confidence, horizon | System looked ahead before acting |
| gcl.interpret | Every cycle | Objective terms, weights, rationale | Goal was set (by LLM or template), never an action |
| gcl.plan | Every cycle | Action steps, committed_step_index=0 | Plan computed under constraints, only first step committed |
| gcl.falsify | Every cycle | Verdict (survives/fails), failed_check, reasoning | Every plan was challenged before commit |
| gcl.commit | When plan survives | Action type, parameters, verdict | Action was committed only after surviving falsification |
| gcl.reject | When plan fails | Action type, failed_check, reasoning | Action was held because falsification found a flaw |

### Fleet-llm-d entries (source: fleet-controller)

| Entry Type | Written When | Content | Proves |
|---|---|---|---|
| fleet.placement.assigned | Cluster selected | Cluster ID, pool, GPU type, score | Workload placed by constraint solver, not arbitrary |
| fleet.model.deployed | Model deployed | Model name, cluster, replicas | Deployment recorded with provenance |
| fleet.routing.shifted | Traffic moved | Pool, weights, reason | Traffic shift recorded with justification |
| fleet.tenant.registered | Tenant onboarded | Tenant ID, quotas | Tenant access recorded |

## Verification

Every chain can be verified independently:

```bash
# Verify all chains are cryptographically intact
GET /api/verify
# Returns: {"all_valid": true, "chains": [...]}

# Query all entries for a specific cycle
GET /api/receipts/chain?correlation_id=gcl-<uuid>
# Returns: ordered list of entries (classify, predict, interpret, plan, falsify, commit/reject)

# Query all entries from a specific source
GET /api/entries?source_id=gcl
GET /api/entries?source_id=fleet-controller
```

## What the Proof Shows

1. **Every decision was governed.** No action committed without a full cycle (classify, predict, interpret, plan, falsify).
2. **Every rejection has a reason.** The failed_check field names exactly what falsification caught.
3. **The LLM never produced an action.** gcl.interpret contains only objective terms and rationale, never action types.
4. **Hard constraints were never violated.** Every committed scale action has replicas within the capacity bound.
5. **The receipt is immutable.** Hash chains verify that no entry was altered after writing.
