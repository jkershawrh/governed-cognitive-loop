#!/usr/bin/env bash
set -euo pipefail

PASS=0
FAIL=0

check() {
  if eval "$2" >/dev/null 2>&1; then
    echo "  [OK] $1"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $1"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== governed-cognitive-loop preflight ==="

check "Python >= 3.9" "python3 -c 'import sys; assert sys.version_info >= (3,9)'"
check "venv active" "python3 -c 'import sys; assert sys.prefix != sys.base_prefix'"
check "numpy importable" "python3 -c 'import numpy'"
check "fastapi importable" "python3 -c 'import fastapi'"
check "pydantic v2" "python3 -c 'import pydantic; assert int(pydantic.VERSION.split(\".\")[0]) >= 2'"
check "httpx importable" "python3 -c 'import httpx'"
check "pytest importable" "python3 -c 'import pytest'"
check "config parses" "python3 -c 'from gcl.config import get_settings; s = get_settings(); assert s.horizon_length > 0'"

if [ "${GCL_LEDGER_SKIP:-}" != "1" ]; then
  check "ledger reachable" "python3 -c '
import httpx, os
url = os.getenv(\"GCL_LEDGER_URL\", \"http://localhost:18099\")
r = httpx.get(f\"{url}/api/summary\", timeout=5)
assert r.status_code == 200
'"
else
  echo "  [SKIP] ledger (GCL_LEDGER_SKIP=1)"
fi

if [ "${GCL_FORCE_DETERMINISTIC:-}" != "1" ]; then
  check "LLM endpoint reachable" "python3 -c '
from gcl.inference.client import is_inference_available
assert is_inference_available()
'"
else
  echo "  [SKIP] LLM endpoint (GCL_FORCE_DETERMINISTIC=1)"
fi

echo ""
echo "Preflight: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
