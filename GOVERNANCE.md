# Governance

Governed Cognitive Loop is an open source project maintained in the open.

## Roles

- **Users** run GCL or integrate it with another system.
- **Contributors** submit issues, designs, documentation, tests, or code.
- **Maintainers** review changes, manage releases, and protect the project's safety boundaries.

The current maintainer is the repository owner, `jkershawrh`. Maintainer membership will expand when contributors demonstrate sustained, constructive participation across multiple changes.

## How decisions are made

Routine changes use lazy consensus through GitHub issues and pull requests. A maintainer may merge a reviewed change when objections are resolved and required checks pass.

Changes to any of the following require a public design issue or architecture decision record before implementation:

- the proposal-only authority boundary;
- a stable contract or its compatibility policy;
- signing, identity, tenancy, or provenance semantics;
- the deterministic ownership of action selection and hard constraints;
- the extension model or a new privileged integration;
- project licensing or governance.

Maintainers document the decision and meaningful dissent. When consensus cannot be reached, the current maintainer makes the decision and records the rationale publicly.

## Safety boundary

GCL produces advisory decision packages. It does not grant execution authority and it does not prove that a proposed action occurred. Changes that blur proposal, authorization, execution, or observed-outcome semantics will not be accepted.

## Releases

Releases use semantic versioning. Until `1.0.0`, public contracts may change between minor versions, but changes must be documented and a migration path should be provided. Stable versioned contracts are not changed in place.

## Conduct

Project participation must be professional, respectful, and focused on the technical work. Harassment, discrimination, threats, and disclosure of private information are not acceptable. Maintainers may remove content or restrict participation to protect the community.

## Changes to governance

Governance changes follow the same public design process as other protected architecture decisions.
