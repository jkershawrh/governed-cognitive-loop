from __future__ import annotations

import base64

import pytest

from gcl.config import Settings, decision_signing_key


def test_base64_decision_signing_key_is_decoded():
    key = bytes(range(32))
    encoded = base64.b64encode(key).decode("ascii")
    settings = Settings(decision_signing_key=f"base64:{encoded}")

    assert decision_signing_key(settings) == key


def test_invalid_base64_decision_signing_key_is_rejected():
    settings = Settings(decision_signing_key="base64:not-valid!!!")

    with pytest.raises(ValueError, match="invalid base64"):
        decision_signing_key(settings)
