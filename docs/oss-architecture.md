# OSS architecture

## Product boundary

Governed Cognitive Loop is a proposal-only governance kernel. It converts evidence into a constrained, falsified, signed, and expiry-bounded `DecisionPackage`. Another system independently decides whether to authorize and execute the proposal.

```text
evidence producers          GCL                         external authorities

TrustyAI Service  ─┐    ┌───────────────┐           ┌─ human approval
EvalHub            ├───>│ evidence ports │           ├─ policy admission
Prometheus         │    ├───────────────┤  signed   ├─ workflow engine
CloudEvents        │    │ governance     │ proposal  ├─ Kubernetes controller
domain systems     ┘    │ kernel         ├──────────>└─ fleet control plane
                       ├───────────────┤
policy and context ────>│ extension ports│
                       └───────┬───────┘
                               │ evidence and outcome records
                               v
                         proof and telemetry sinks
```

GCL owns the decision record. It does not own source measurements, external policy authority, admission, actuation, rollback, or proof-store truth.

## Why a kernel with ports

The current implementation proves the decision cycle in an inference-fleet domain. Making each upstream project a first-class dependency would replace one tightly coupled architecture with another. The OSS design keeps a small, stable kernel and places ecosystem details in adapters.

The kernel should know that evidence has a producer, subject, scope, timestamp, schema, confidence, and provenance. It should not know the TrustyAI REST response, Prometheus HTTP API, or a fleet controller endpoint.

## Architectural layers

### 1. Versioned contracts

Contracts are the most stable surface:

- `EvidenceEnvelope`: normalized fact or evaluation result with provenance.
- `Constraint`: a hard or soft bound justified by evidence references.
- `ObjectiveSpec`: terms and weights, with no action fields.
- `Candidate`: a proposed action in a registered action namespace.
- `FalsificationResult`: disconfirmation checks and evidence references.
- `DecisionPackage`: selected candidate, rejected alternatives, scope, identity, expiry, and signature.
- `OutcomeRecord`: independently observed result linked to a package.

Versioned contracts are additive within a major version. New producer-specific data belongs in a namespaced extension object, not in the core schema.

### 2. Governance kernel

The kernel owns the deterministic lifecycle:

1. Validate and normalize evidence.
2. Classify constraints.
3. Forecast a bounded horizon when the policy requires it.
4. Interpret an objective, optionally using an LLM with a deterministic fallback.
5. Generate candidates with a deterministic controller or registered domain planner.
6. Enforce hard constraints.
7. Falsify the selected candidate.
8. Build and sign a `DecisionPackage`.
9. Offer the package to a proposal sink.
10. Correlate later outcomes without claiming them from transport acknowledgement.

The kernel must run with no network dependency. The standalone defaults are in-memory evidence input, deterministic interpretation, a no-op proposal sink, an in-memory proof recorder, and an ephemeral test signer that is prohibited in production.

### 3. Ports

Ports are narrow interfaces owned by GCL:

| Port | Direction | Responsibility |
|---|---|---|
| `EvidenceSource` | inbound | Delivers normalized evidence envelopes or batches. |
| `ContextProvider` | inbound | Supplies scoped inventory, limits, or facts needed by policy. |
| `PolicyCheck` | inbound | Evaluates an additional deterministic allow, deny, or constraint rule. |
| `ObjectiveInterpreter` | internal | Produces an objective only. It cannot produce an action. |
| `Planner` | internal | Produces candidates for a registered action namespace. |
| `FalsificationCheck` | internal | Attempts to disconfirm one candidate. |
| `ProposalSink` | outbound | Delivers a signed package to an external authority. |
| `ProofRecorder` | outbound | Records evidence and package receipts without granting authority. |
| `OutcomeSource` | inbound | Supplies independently observed outcomes. |
| `KeyProvider` | inbound | Supplies signing identity and key handles. |
| `TelemetrySink` | outbound | Emits metrics, logs, and traces with correlation identifiers. |

Python protocols come first. Remote HTTP, CloudEvents, or gRPC bindings can be standardized later through a conformance kit. This avoids prematurely turning every in-process extension into a network service.

### 4. Adapters

Adapters translate an external contract into one port. They retain the upstream payload digest and identity so a decision can be audited without copying the upstream domain model into GCL.

An adapter must fail explicitly. It cannot silently convert stale, unverified, cross-tenant, or malformed input into trusted evidence.

### 5. Hosts

The same kernel can run in several hosts:

- Python library for tests and embedded applications.
- Standalone HTTP service for a single team or local evaluation.
- Multi-tenant service behind an authenticating proxy.
- Kubernetes deployment with adapter configuration.
- Event consumer for asynchronous CloudEvents.

A future Kubernetes custom resource may configure a GCL deployment. It must not make GCL an infrastructure actuator.

## EvidenceEnvelope v1 target

The portable evidence contract should include:

```yaml
apiVersion: gcl.io/v1alpha1
kind: EvidenceEnvelope
metadata:
  id: "producer-unique-id"
  correlationId: "trace-or-workflow-id"
  causationId: "optional-parent-id"
  observedAt: "2026-08-31T12:00:00Z"
  expiresAt: "2026-08-31T12:15:00Z"
  producer: "https://trustyai.example/services/default"
  schema: "https://trustyai.org/schemas/metric-result/v1"
scope:
  tenant: "team-a"
  namespace: "models"
subject:
  type: "model"
  id: "fraud-detector-v7"
measurement:
  name: "data-drift"
  value: 0.31
  unit: "ratio"
  threshold: 0.20
  status: "failed"
assurance:
  confidence: 0.96
  digest: "sha256:..."
extensions:
  trustyai.org/job-id: "..."
```

The schema is intentionally a normalization boundary, not a replacement for the complete upstream result. `assurance.digest` and an optional immutable URI bind the envelope to the source artifact.

## Action namespaces

The current DecisionPackage accepts fleet action classes. The OSS model should use registered namespaces:

- `governance.hold`
- `governance.request_review`
- `routing.quarantine`
- `deployment.rollback`
- `fleet.scale`
- vendor or project namespaces such as `example.org/custom_action`

The kernel validates namespace registration, parameter schema, consequence class, and required falsification checks. A planner plugin owns domain semantics. GCL continues to emit the action as a proposal only.

DecisionPackage v1 remains unchanged for compatibility. General action namespaces belong in DecisionPackage v2 after an architecture decision record and migration plan.

## Integration points

### TrustyAI Service

Consume scheduled drift and fairness metrics or service alerts. The adapter maps the model identity, metric window, threshold, status, namespace, and result digest into evidence. GCL may then propose review, hold, route, scale, or migration actions according to an installed policy pack.

TrustyAI owns metric computation. GCL must not reimplement or reinterpret a passing metric as failing.

### EvalHub

Consume terminal evaluation jobs and collection compliance results. This is the preferred pre-deployment integration because EvalHub already unifies multiple evaluation providers and tracks artifacts. GCL should reference EvalHub result artifacts and translate their status into promotion constraints.

The first demonstration should show a failed safety collection producing a signed `governance.hold` or `governance.request_review` proposal.

### Guardrails

Use aggregate detector signals over a window, not the synchronous token path. GCL is not a request-time guardrail. A detector-rate or severity change can become evidence for a slower operational proposal such as quarantine, rerouting, or capacity isolation.

### Prometheus and Alertmanager

Prometheus range queries provide metric evidence; Alertmanager webhooks provide state transitions. The adapter records query, time range, labels, source URL, and response digest. Alerts are evidence, not commands.

### OpenTelemetry

Trace and baggage identifiers connect source evaluation, GCL cycle, package delivery, external authorization, and observed outcome. OpenTelemetry is telemetry correlation, not the immutable proof store.

### OPA and policy engines

OPA/Rego can implement deterministic `PolicyCheck` extensions at evidence admission, candidate validation, or package egress. Policy results and bundle revisions become evidence references. OPA does not sign the DecisionPackage unless it is separately configured as the external authority.

### CloudEvents

CloudEvents is the preferred transport envelope for asynchronous evidence and proposals. GCL pins accepted event types and schema versions per adapter. A generic CloudEvents adapter dispatches to a producer-specific normalizer instead of accepting arbitrary JSON as trusted evidence.

### Proof stores

`are-immutable-ledger` remains the first proof adapter. Other append-only stores, OCI artifacts, transparency logs, or signed object storage can implement `ProofRecorder`. Receipt success never changes proposal authority.

### Proposal consumers

Initial consumers include fleet-llm-d, generic webhooks, human-review workflows, and Kubernetes admission or reconciliation systems. Each consumer independently authenticates, verifies, authorizes, and acts. A `202 Accepted` response means delivery or admission only.

## Trust and failure model

Every adapter documents these decisions:

- producer authentication and workload identity;
- tenant, namespace, and subject mapping;
- supported schema versions;
- maximum evidence age and clock-skew handling;
- replay and idempotency behavior;
- digest or artifact verification;
- timeout and retry policy;
- failure-open, failure-closed, or degraded behavior;
- redaction and retention expectations.

The safe default is to reject malformed or cross-scope evidence, decline to emit a consequential proposal when required evidence is unavailable, and retain a reasoned rejection record.

## Repository strategy

Keep a monorepo through 1.0 so contracts, conformance fixtures, core, and first-party adapters evolve together:

```text
gcl/
  core/                 # target governance kernel
  contracts/            # versioned models and schema exports
  ports/                 # extension protocols
  adapters/
    builtin/             # memory, no-op, HTTP, CloudEvents
    deepfield/           # current evidence producer
    fleet_llm_d/         # current proposal consumer
    trustyai/            # Service and EvalHub evidence
    prometheus/          # metrics and alerts
    opa/                 # deterministic policy checks
    proof/               # ARE and generic proof sinks
  hosts/
    api/                 # FastAPI host
    worker/              # asynchronous event host
```

This is a target layout. Migration should be incremental and preserve the existing `gcl.adapter` imports until a documented major-version transition.

## First three milestones

1. **OSS foundation:** license, governance, standalone documentation, stable v1 contract, and honest maturity statements.
2. **Portable core:** generic evidence ingress, protocols for sources and sinks, standalone defaults, and conformance fixtures.
3. **TrustyAI proof:** Service and EvalHub adapters plus a reproducible result-to-proposal demonstration on OpenShift and locally.

Do not add an operator custom resource before the portable core and TrustyAI proof show maintainer demand. An operator integration creates a long-lived support surface and should follow, not lead, the contract.
