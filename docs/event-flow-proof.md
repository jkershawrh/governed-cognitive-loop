# Event flow and evidence boundary

This document describes the implemented GCL producer boundary. It does not claim that the wider ecosystem runtime is assembled or that a proposal executed.

## Decision flow

```text
rev_deepfield or conforming producer
  observation and forecast evidence
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
      - proposer identity and authority attestation
      - expiry, correlation, causation, and idempotency
  [7] canonical digest and signature
  [8] gcl.decision_package.proposed
      execution_verified=false
      |
      | CloudEvents 1.0 structured event
      v
proposer authority endpoint
  acknowledgement only
      |
      v
governance-strata -> ARE -> FleetIntent/FleetOperation -> fleet-llm-d
  external contracts and runtimes, not proven by this repository's unit suite
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

These records demonstrate local decision sequencing. Only an ARE receipt-chain verification can establish immutable ecosystem audit truth. The in-memory ledger used by standalone tests cannot establish that truth.

## What local tests establish

Local tests establish:

1. The objective interpreter does not compute control actions.
2. Candidate plans honor the deterministic constraint checks covered by the suite.
3. A surviving candidate is encoded in the strict DecisionPackage v1 model.
4. Package canonicalization, digest, signature, expiry, and tamper checks execute.
5. CloudEvent IDs and transport headers are deterministic.
6. Proposer acknowledgement never sets execution verification.
7. Missing passport and authority dependencies fail closed in production mode.
8. Legacy fleet v1 HMAC submission requires an explicit non-production compatibility flag.

Local tests do not establish:

- an ARE execution grant;
- fleet actuation or verified observed state;
- immutable external ledger receipts;
- multi-cluster, OpenShift, performance, chaos, soak, or security promotion evidence.

See [DecisionPackage v1](decision-package-v1.md) for the full contract.
