# governed-cognitive-loop

LLM-MPC with evidence-based constraint classification and hypothesis falsification before commit.

## Build and run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Test

```bash
python3 -m pytest tests/ -q
```

## Verify (full suite)

```bash
GCL_FORCE_DETERMINISTIC=1 GCL_LEDGER_SKIP=1 bash verify.sh
```

## Conventions

- Python 3.12+, Pydantic v2, FastAPI, numpy
- CDD contracts first, then TDD, then BDD, then EDD rubric
- No em-dashes anywhere in generated output (use commas, colons, periods, parentheses)
- The LLM never computes the committed control action. A deterministic controller owns optimization.
- Do not claim optimality. The guarantee is hard-constraint satisfaction and falsification-gated commit.
- Every LLM call site must have a deterministic fallback.

## Architecture

See `docs/architecture.md` for the honesty boundary and component responsibilities.
