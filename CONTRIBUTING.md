# Contributing to Governed Cognitive Loop

Thank you for helping make governed automation more inspectable and interoperable.

## Start with the boundary

Before writing code, read:

- [OSS architecture](docs/oss-architecture.md)
- [DecisionPackage v1](docs/decision-package-v1.md)
- [Governance](GOVERNANCE.md)
- [Security policy](SECURITY.md)

GCL is proposal-only. An integration may deliver a proposal to an external authority, but it must not claim that acknowledgement is authorization, execution, or verified outcome.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
GCL_RUNTIME_MODE=standalone-test GCL_FORCE_DETERMINISTIC=1 python -m pytest -q
```

Run lint and the full local verification before opening a pull request:

```bash
python -m ruff check gcl tests
GCL_FORCE_DETERMINISTIC=1 GCL_LEDGER_SKIP=1 bash verify.sh
```

## Change workflow

1. Open an issue for a new integration, contract change, or architectural change.
2. Add or update a contract test before implementation when behavior crosses a system boundary.
3. Keep the governance kernel independent from vendor SDKs and deployment platforms.
4. Include deterministic behavior for every optional LLM path.
5. Document failure behavior, identity, tenancy, freshness, and idempotency for integrations.
6. Update user-facing documentation and release notes with the code.

Small fixes may go directly to a pull request.

## Integration acceptance criteria

An integration must state:

- which port it implements;
- the external contract and supported versions;
- authentication and authorization assumptions;
- tenant and scope mapping;
- freshness, replay, and idempotency behavior;
- whether failure is open, closed, or degraded;
- how provenance is retained;
- how it can be tested without the external service;
- why it belongs in the main repository rather than a separate package.

Prefer a thin adapter over importing another project's domain model into the core.

## Pull requests

Pull requests should be focused, tested, and explain the user-visible outcome. By submitting a contribution, you agree that it is licensed under Apache License 2.0 as described in [LICENSE](LICENSE).
