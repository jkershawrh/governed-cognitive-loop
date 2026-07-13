# Data Contracts

Cycle-internal contracts are Pydantic v2 models in `gcl/domain/contracts.py`. The ecosystem output contract is defined in `gcl/domain/decision_package.py`.

## Evidence

A single observation from the system: a named metric, its value, and a timestamp. Evidence is the raw input that justifies constraints.

## Constraint

A typed constraint with a bound, a hard/soft flag, and the evidence that justifies it. Every constraint must carry at least one justifying evidence id or it is invalid and must be dropped. Constraints from deterministic rules carry higher confidence than those from the LLM.

Types: capacity, priority, compliance, residency, budget, latency, custom.

## Trajectory

A predicted trajectory over a planning horizon: a list of points (each with a step index and value), the number of horizon steps, and a confidence score derived from the prediction quality.

## ObjectiveSpec

The objective for the controller: a list of cost terms with weights, a partition of constraints into hard and soft ids, and a rationale explaining the interpretation. Produced by the ObjectiveInterpreter (LLM or deterministic template). Never contains an action.

## ActionPlan

A sequence of candidate action steps over the horizon. Each step has an action type (scale, pre_warm, shed_load, no_action), parameters, and a predicted effect. Only the first step (index 0) is selected for the package. The receding horizon discipline means the plan is recomputed each cycle.

## FalsificationResult

The result of pre-commit disconfirmation: a verdict (survives or fails), the failed check name (if any), reasoning, and the evidence ids consulted.

## LoopCycle

A complete record of one decision cycle: the constraints snapshot, trajectory, objective, action plan, falsification result, whether a decision package was committed, proposal acknowledgement, package digest, and the correlation id linking cycle records. `committed` does not mean infrastructure execution. `execution_verified` is false in GCL proposal responses.

## DecisionPackage v1

The signed, expiry-bounded output contract contains proposer and authority attestations, constraints, candidates, rejected alternatives, falsification results, confidence, SHA-256 evidence references, and correlation, causation, and idempotency IDs. It is transported as a structured CloudEvents 1.0 envelope.

See [DecisionPackage v1](decision-package-v1.md) for validation, signing, schema endpoints, security modes, and the ownership boundary.
