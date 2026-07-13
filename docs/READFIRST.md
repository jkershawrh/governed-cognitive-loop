# READFIRST: current boundaries and assumptions

## Ecosystem owners

- `rev_deepfield` owns observations, findings, and forecasts.
- GCL owns decision synthesis, alternatives, falsification, and `DecisionPackage`.
- agent-promotion owns proposer autonomy ceilings.
- governance-strata owns transaction lifecycle.
- ARE owns execution authorization and immutable receipt truth.
- fleet-llm-d owns authorized fleet desired, observed, and operation state.

Producer repositories own their schemas. This repository therefore exports its versioned DecisionPackage and CloudEvent schemas and does not redefine downstream execution or ledger contracts.

## Implemented integration boundary

GCL publishes a signed, expiry-bounded `DecisionPackage` as a structured CloudEvents 1.0 event to the configured proposer endpoint. An acknowledgement means proposal transport only. It never means verified execution.

The legacy fleet `/api/v1/intents` HMAC adapter is disabled by default, always disabled in production, and available only behind an explicitly named development compatibility flag.

## Assumptions

1. The optional LLM endpoint follows an OpenAI-compatible chat completions API.
2. Production passport and authority services are configured and reachable. GCL fails closed if either check cannot authorize the proposal.
3. `GCL_DECISION_SIGNING_KEY` is delivered by external secret management and contains at least 32 bytes.
4. Tests deliberately set `GCL_RUNTIME_MODE=standalone-test`; that mode is never a production configuration.
5. Local in-memory ledger records and mocked proposer responses are component evidence only.

See [DecisionPackage v1](decision-package-v1.md) and [Event flow and evidence boundary](event-flow-proof.md).
