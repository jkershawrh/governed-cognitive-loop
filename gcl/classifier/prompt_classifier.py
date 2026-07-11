from __future__ import annotations

import re
from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class PromptTier(str, Enum):
    SIMPLE = "simple"
    STANDARD = "standard"
    COMPLEX = "complex"


class PromptClassification(BaseModel):
    tier: PromptTier
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    estimated_tokens: int = 50


class PromptClassifier:
    def __init__(self) -> None:
        config_path = (
            Path(__file__).resolve().parent.parent.parent
            / "config"
            / "defaults"
            / "semantic_routing.yaml"
        )
        with open(config_path) as f:
            config = yaml.safe_load(f)
        self._rules: list[dict] = config.get("rules", [])
        self._tiers: dict = config.get("tiers", {})

    def classify(self, prompt: str) -> PromptClassification:
        prompt_lower = prompt.strip().lower()
        for rule in self._rules:
            if re.search(rule["pattern"], prompt_lower):
                tier = PromptTier(rule["tier"])
                return PromptClassification(
                    tier=tier,
                    confidence=rule.get("confidence", 0.8),
                    reasoning=f"Matched rule: {rule['pattern']}",
                    estimated_tokens=self._tiers.get(tier.value, {}).get(
                        "max_tokens", 100
                    ),
                )
        return PromptClassification(
            tier=PromptTier.STANDARD,
            confidence=0.6,
            reasoning="No rule matched, defaulting to standard",
            estimated_tokens=100,
        )

    def get_models_for_tier(self, tier: PromptTier) -> list[str]:
        return self._tiers.get(tier.value, {}).get("models", [])
