# Security policy

## Supported versions

GCL is currently pre-1.0. Security fixes are applied to the latest release and the default branch. A formal long-term support policy will be established before 1.0.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub's private vulnerability reporting for this repository:

`https://github.com/jkershawrh/governed-cognitive-loop/security/advisories/new`

Include the affected version or commit, reproduction steps, impact, and any suggested mitigation. Please avoid accessing data or systems that you do not own.

## Security invariants

The following behaviors are security boundaries:

- GCL emits proposals, not authorization grants or actuator commands.
- A transport acknowledgement never proves execution.
- Production packages require externally supplied signing material.
- Package verification includes identity, digest, signature, scope, and expiry.
- LLM output cannot directly define the committed action or bypass hard constraints.
- Evidence and evaluation results are untrusted until their producer, scope, schema, freshness, and provenance are validated.
- Optional integrations must not silently widen authority when they are unavailable.

Reports that demonstrate a violation of one of these invariants are treated as security issues even if no conventional code execution is involved.

## Deployment guidance

Production operators should use workload identity, external secret management, least-privilege network policy, read-only filesystems where possible, and independent authorization at the proposal consumer. The built-in standalone mode and deterministic test key are not production configurations.
