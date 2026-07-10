# Architecture

## Control loop

```
Signals -> Classify constraints (from evidence)
        -> Predict horizon + Interpret objective (LLM) + Optimize under constraints (deterministic)
        -> Falsify the committed action (disconfirmation, pre-commit)
        -> Commit the survivor (first step only)
        -> Re-measure -> repeat
```

## The honesty boundary

The LLM interprets context into an objective and predicts disturbances. That is all.

The LLM never computes the committed control action and never performs constraint satisfaction. A deterministic controller owns optimization and the hard-constraint guarantee.

This system does not claim optimality. The objective is LLM-specified, so classical optimality guarantees do not hold. The guarantee is: hard-constraint satisfaction and falsification-gated commit.

## Components

| Component | Responsibility | LLM involvement |
|---|---|---|
| ConstraintClassifier | Evidence to typed constraints | Second stage only, for ambiguous cases |
| HorizonPredictor | Current state to predicted trajectory | None |
| ObjectiveInterpreter | Context to ObjectiveSpec | Primary (with deterministic fallback) |
| Controller | Trajectory + objective + constraints to ActionPlan | None (deterministic, numpy) |
| FalsificationGate | Pre-commit disconfirmation | Optional adversarial probe |
| Committer | Actuate or reject, record to ledger | None |
| LoopDriver | Orchestrates the cycle | None |
| FleetAdapter | Maps actions to fleet intents | None |

## Receding horizon

The controller computes actions over the full horizon but marks only the first step as committed. After committing (or rejecting), the loop re-measures and re-plans from the new state.

## Falsification

The FalsificationGate treats the committed step as a hypothesis: "this action produces the intended outcome under the predicted conditions." It runs disconfirmation checks to try to break this hypothesis. Only actions that survive falsification are committed.

## Ledger chain

Each cycle writes a chain under one correlation id: classified constraints, predicted trajectory, interpreted objective, proposed action, falsification result, and commit/rejection outcome.
