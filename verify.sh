#!/usr/bin/env bash
set -euo pipefail

echo "=== governed-cognitive-loop verify ==="

echo ""
echo "--- Preflight ---"
bash preflight.sh

echo ""
echo "--- Em-dash check ---"
if grep -rn $'\xe2\x80\x94' gcl/ docs/ tests/ 2>/dev/null; then
  echo "FAIL: em-dash found in source"
  exit 1
else
  echo "  [OK] No em-dashes found"
fi

echo ""
echo "--- Unit, BDD, and EDD tests ---"
python3 -m pytest tests/ -q --tb=short

echo ""
echo "--- LLM boundary assertion ---"
python3 -m pytest tests/test_objective_interpreter.py::TestHonestyBoundary -v --tb=short

echo ""
echo "--- Hard constraint property tests ---"
python3 -m pytest tests/test_properties.py -v --tb=short

echo ""
echo "--- Falsification rejection test ---"
python3 -m pytest tests/test_falsification_gate.py::TestFalsificationGate::test_known_bad_action_rejected -v --tb=short

echo ""
echo "--- End-to-end cycle ---"
python3 -m pytest tests/test_loop_driver.py::TestLoopDriver::test_full_cycle_produces_complete_loop_cycle -v --tb=short

echo ""
echo "--- EDD rubric ---"
python3 -m pytest tests/test_rubrics.py -v --tb=short

echo ""
echo "verify.sh: ALL CHECKS PASSED"
