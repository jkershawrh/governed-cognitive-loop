# DecisionPackage v1 contract

`DecisionPackage` is the authoritative output of the Governed Cognitive Loop. It is a proposal, not an execution grant and not evidence that infrastructure changed.

## Ownership boundary

GCL owns decision synthesis, candidate selection, rejected alternatives, falsification, and package signing. Agent-promotion owns the proposer's autonomy ceiling. Governance-strata owns transaction progression. ARE owns final execution authorization and ledger truth. Fleet owns infrastructure reconciliation.

The ordinary path is:

```text
evidence -> GCL -> signed DecisionPackage CloudEvent -> proposer authority
         -> governance-strata -> ARE -> FleetIntent/FleetOperation -> fleet controller
```

GCL never invokes the fleet execution API on this path. A successful proposer HTTP response means only that the package was accepted for asynchronous processing. Every GCL proposal result sets `execution_verified` to `false`.

## Required fields

The versioned model is `gcl.llm-d.ai/decision-package/v1`. It carries:

- an expiry-bounded package ID, correlation ID, causation ID, and idempotency ID;
- tenant and zone scope;
- SPIFFE-compatible proposer identity and trust domain;
- passport and agent-promotion authority decision digests, action class, consequence score, and autonomy ceiling;
- typed constraints and their SHA-256 evidence references;
- candidates, the selected candidate, and explicitly rejected alternatives;
- falsification results tied to candidate IDs;
- bounded confidence and the complete unique evidence digest set;
- a canonical SHA-256 payload digest, key ID, algorithm, and signature.

Candidate and authority action classes are restricted to `fleet.deploy`, `fleet.scale`, `fleet.route`, `fleet.prewarm`, `fleet.shed_load`, `fleet.migrate`, and `fleet.kv_transfer`. Internal `no_action` decisions emit no package. Legacy `fleet.alert`, `fleet.rollback`, and `fleet.observe` candidates are rejected rather than silently entering the governed execution path.

Unknown fields are rejected. Timestamps must be timezone-aware. Package expiry cannot outlive the authority attestation. Nested evidence references must exist in the package evidence set. Candidate and selection references are validated.

## Canonical digest and signature

Canonical bytes are UTF-8 JSON with sorted keys, compact separators, and no ASCII rewriting. The digest is `sha256:<64 lowercase hex>`. The current target contract uses `HMAC-SHA256` over the canonical package bytes and requires at least 32 bytes of key material. Runtime key distribution belongs to the deployment identity and secret-management layer. This slice does not claim that production key rotation or external verification infrastructure is complete.

Verification checks the key ID when requested, constant-time signature equality, and the package validity window. A package at or after its expiry is invalid.

## CloudEvents 1.0

The proposer adapter sends structured CloudEvents with content type `application/cloudevents+json` to:

```text
POST {GCL_PROPOSER_URL}/api/v1/proposals/decision-packages
```

The event type is `ai.llm-d.gcl.decision-package.v1`. Its deterministic event ID is derived from the package ID, package digest, and event type. The envelope carries correlation, causation, idempotency, tenant, zone, trace, expiry, and evidence extensions.

Runtime JSON Schema exports are available at:

```text
GET /api/v1/contracts/decision-package-v1/schema
GET /api/v1/contracts/decision-package-cloudevent-v1/schema
```

The producer repository owns these schemas. Downstream releases should pin the producer version rather than copy and redefine the contract.

## Security modes

`GCL_RUNTIME_MODE=production` is fail closed. Missing or unreachable passport and authority services deny proposal construction. Production also requires explicit signing key material.

Tests must deliberately set `GCL_RUNTIME_MODE=standalone-test`. Only that mode permits labeled test-only passport and authority bypasses and a deterministic test signing key.

Legacy `/api/v1/intents` HMAC submission is disabled by default and always disabled in production. It is available only when both conditions are true:

```text
GCL_RUNTIME_MODE=development
GCL_ALLOW_LEGACY_FLEET_HMAC_DEVELOPMENT_COMPAT=true
```

Even in that compatibility mode, its response is transport acknowledgement only and `execution_verified` remains `false`.

## Evidence level

Focused model, signing, expiry, tamper, schema, CloudEvent, proposer transport, and fail-closed tests execute in this repository. This is contract evidence only. It is not evidence of a restored multi-repository production loop, live fleet actuation, OpenShift operation, external ledger receipts, or release maturity.
