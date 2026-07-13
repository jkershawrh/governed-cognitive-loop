# Event flow and evidence boundary

This document describes the implemented GCL producer boundary. It does not claim that the wider ecosystem runtime is assembled or that a proposal executed.

## Decision flow

```text
deepfield-fleet
  observation and forecast evidence
  CloudEvents 1.0 -> POST /api/v1/events/deepfield
      |
      v
governed-cognitive-loop
  [1] gcl.classify
  [2] gcl.predict
  [3] gcl.interpret
  [4] gcl.plan
  [5] gcl.falsify
  [6] construct DecisionPackage v1
      - constraints and evidence SHA-256 references
      - selected candidate and rejected alternatives
      - falsification results and confidence
      - proposer identity and optional non-authoritative compatibility metadata
      - expiry, correlation, causation, and idempotency
  [7] canonical digest and signature
  [8] gcl.decision_package.proposed
      execution_verified=false
      |
      | CloudEvents 1.0 structured event
      v
fleet-llm-d /api/v2/intents
  admission acknowledgement only
      |
      v
FleetIntent/FleetOperation -> fleet authorization -> actuation
  external runtime behavior, not proven by this repository's unit suite
      |
      v
are-immutable-ledger
  evidence receipts and proof verification only
```

## GCL record types

| Entry type | Written when | Evidence |
|---|---|---|
| `gcl.classify` | A cycle derives constraints | Constraint snapshot and source evidence IDs |
| `gcl.predict` | A cycle predicts a trajectory | Points, horizon, and confidence |
| `gcl.interpret` | A cycle constructs an objective | Terms, weights, and rationale, never an action |
| `gcl.plan` | The deterministic controller builds candidates | Candidate steps and selected index |
| `gcl.falsify` | The selected candidate is challenged | Verdict, reasoning, and failed check |
| `gcl.decision_package.proposed` | A proposer endpoint accepts a signed package | Package ID, digest, accepted status, and `execution_verified=false` |
| `gcl.decision_package.proposal_pending` | Delivery is deferred or no endpoint is configured | Package ID, digest, pending status, and `execution_verified=false` |
| `gcl.decision_package.proposal_rejected` | The proposer endpoint rejects the package | Package ID, digest, rejection status, and `execution_verified=false` |
| `gcl.reject` | A plan or package is rejected | Named failure and reasoning |

These records demonstrate local decision sequencing. Only an `are-immutable-ledger` receipt-chain verification can establish external immutable proof. A valid receipt proves that evidence was recorded; it does not grant authority or prove actuation. The in-memory ledger used by standalone tests cannot establish external proof.

## What local tests establish

Local tests establish:

1. The objective interpreter does not compute control actions.
2. Candidate plans honor the deterministic constraint checks covered by the suite.
3. A surviving candidate is encoded in the strict DecisionPackage v1 model.
4. DeepField source identity and sink credentials are enforced in production; correlation, causation, idempotency, and evidence digests are preserved.
5. Package canonicalization, digest, signature, expiry, and tamper checks execute.
6. CloudEvent IDs and transport headers are deterministic.
7. Fleet acknowledgement never sets execution verification.
8. The core loop never calls passport or external execution-authority gates.
9. Optional agent-promotion results are marked non-authoritative and do not suppress submission.
10. Legacy fleet v1 HMAC submission requires an explicit non-production compatibility flag.

Local tests do not establish:

- fleet actuation or verified observed state;
- immutable external `are-immutable-ledger` receipts;
- multi-cluster, OpenShift, performance, chaos, soak, or security promotion evidence.

See [DecisionPackage v1](decision-package-v1.md) for the full contract.
