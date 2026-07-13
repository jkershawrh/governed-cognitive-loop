# READFIRST: current boundaries and assumptions

## Ecosystem owners

- `deepfield-fleet` owns observations, findings, and forecasts.
- GCL owns decision synthesis, alternatives, falsification, and `DecisionPackage`.
- `fleet-llm-d` owns intent admission, execution authorization, desired state, observed state, operation state, and actuation.
- [`jkershawrh/are-immutable-ledger`](https://github.com/jkershawrh/are-immutable-ledger) owns immutable evidence receipts and proof verification. A receipt is never a credential or execution grant.
- agent-promotion is optional, non-authoritative proposer-ceiling compatibility metadata.

The separate `srex-dev/are` and `governance-strata` repositories are not runtime owners in this ecosystem.

Producer repositories own their schemas. This repository therefore exports its versioned DecisionPackage and CloudEvent schemas and does not redefine downstream execution or ledger contracts.

## Implemented integration boundary

GCL consumes DeepField-owned structured CloudEvents at `POST /api/v1/events/deepfield`. It accepts the pinned observation, finding, forecast, and advisory-remediation v1 identities, rejects expired or type/schema-mismatched events, and preserves their correlation, causation, idempotency, and evidence digests.

Production trusts only `GCL_DEEPFIELD_EVENT_SOURCE` and requires `GCL_DEEPFIELD_EVENT_BEARER_TOKEN`. Manual signal, direct fleet-metric, and legacy classification ingestion endpoints are non-production compatibility surfaces.

GCL publishes a signed, expiry-bounded advisory `DecisionPackage` as a structured CloudEvents 1.0 event directly to fleet-llm-d's `/api/v2/intents` endpoint. An acknowledgement means fleet admission only. It never means verified execution.

The legacy fleet `/api/v1/intents` HMAC adapter is disabled by default, always disabled in production, and available only behind an explicitly named development compatibility flag.

## Assumptions

1. The optional LLM endpoint follows an OpenAI-compatible chat completions API.
2. `GCL_DECISION_SIGNING_KEY` is delivered by external secret management and contains at least 32 bytes.
3. Production fleet submission uses an OIDC credential; fleet-llm-d owns authorization after admission.
4. Tests deliberately set `GCL_RUNTIME_MODE=standalone-test`; that mode is never a production configuration.
5. Local in-memory records and mocked fleet responses are component evidence only.

See [DecisionPackage v1](decision-package-v1.md) and [Event flow and evidence boundary](event-flow-proof.md).
