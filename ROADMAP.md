# Roadmap

This roadmap describes intent, not a release commitment. Work is ordered by dependency and risk.

## 0.1: OSS foundation

- Apache License 2.0 and public project governance.
- Standalone positioning and explicit safety boundary.
- Documented core, port, adapter, and hosting architecture.
- Preserve the working inference-fleet integration as the first reference adapter.
- Keep DecisionPackage v1 compatible.

## 0.2: Portable evidence and proposal ports

- Add a versioned `EvidenceEnvelope` independent of any producer.
- Add generic CloudEvents and HTTP evidence ingestion.
- Define typed `EvidenceSource`, `ProposalSink`, `ProofRecorder`, `OutcomeSource`, and `KeyProvider` protocols.
- Make the no-op proposal sink and in-memory proof recorder first-class standalone defaults.
- Move DeepField, fleet-llm-d, and ARE-specific behavior behind adapters.
- Rename ambiguous internal commit language in the v2 API while preserving v1 compatibility.

Exit criteria: GCL runs a complete, signed cycle without importing or configuring any ecosystem-specific adapter.

## 0.3: Responsible-AI integrations

- TrustyAI Service metric and alert adapter.
- EvalHub completed-job and collection-result adapter.
- Prometheus query and alert adapter.
- OpenTelemetry provenance correlation.
- Reference policy packs for drift, fairness, safety, and evaluation gates.

Exit criteria: a reproducible demo turns a TrustyAI or EvalHub result into a signed, expiry-bounded proposal, with no execution authority in GCL.

## 0.4: Policy and proof ecosystem

- OPA/Rego policy-check extension.
- Generic webhook and CloudEvents proposal sinks.
- Sigstore-compatible key and verification exploration.
- Pluggable append-only proof stores and OCI evidence references.
- Conformance kit for third-party adapters.

## 0.5: Kubernetes reference deployment

- Helm chart or Kustomize base with secure defaults.
- ServiceAccount, RBAC, NetworkPolicy, probes, metrics, and OpenTelemetry.
- Namespace and tenant isolation tests.
- Optional controller for GCL configuration, never for infrastructure actuation.

## 1.0: Stable governance kernel

- Stable core contracts and compatibility policy.
- Threat model and independent security review.
- Multi-cluster and failure-mode qualification.
- Documented performance envelope and at least two independent proposal consumers.
- Documented maintainer and release process with more than one active maintainer.

## Explicitly out of scope

- Owning infrastructure execution or rollback.
- Replacing TrustyAI, EvalHub, Prometheus, OPA, or workflow engines.
- Treating an LLM as a policy authority or constraint solver.
- Claiming optimality from an LLM-framed objective.
- Building a universal schema that copies every upstream payload.
