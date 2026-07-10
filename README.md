# governed-cognitive-loop

LLM-MPC with evidence-based constraint classification and hypothesis falsification before commit.

## What this is

A governed control loop that combines an LLM with a deterministic Model Predictive Controller (MPC) for autonomous infrastructure decisions: scaling, pre-warming, and load-shedding.

The loop classifies which constraints apply from evidence, plans an action over a horizon under those constraints, tries to disprove that action before committing it, commits only what survives, then re-measures and re-plans.

## The honesty boundary

- The LLM interprets context into an objective and constraint weighting, and predicts disturbances. That is all.
- The LLM never computes the committed control action and never performs constraint satisfaction. A deterministic controller owns optimization and owns the hard-constraint guarantee.
- This system does not claim optimality. Because the objective is LLM-specified, classical optimality guarantees do not hold. The guarantee this system provides is: hard-constraint satisfaction and falsification-gated commit.
- Falsification seeks disconfirmation. It tries to break the proposed action, not to confirm it.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
GCL_FORCE_DETERMINISTIC=1 GCL_LEDGER_SKIP=1 bash verify.sh
```
