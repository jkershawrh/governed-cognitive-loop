import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config" / "defaults"


def _load_yaml(name: str) -> dict:
    path = _CONFIG_DIR / name
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


class Settings(BaseSettings):
    horizon_length: int = Field(default=10, gt=0)
    confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    falsification_confidence_floor: float = Field(default=0.5, ge=0.0, le=1.0)
    max_constraint_age_seconds: int = Field(default=300, gt=0)
    llm_timeout_seconds: int = Field(default=30, gt=0)
    ledger_timeout_seconds: int = Field(default=5, gt=0)
    warmup_time_multiplier: float = Field(default=1.5, gt=0.0)
    capacity_headroom_fraction: float = Field(default=0.1, ge=0.0, le=1.0)

    llm_api_base: str = ""
    llm_api_key: str = ""
    llm_model: str = "granite-3-2-8b-instruct-cpu"
    ledger_url: str = ""
    fleet_url: str = ""
    force_deterministic: bool = False

    model_config = {"env_prefix": "GCL_"}


@lru_cache
def get_settings() -> Settings:
    defaults = _load_yaml("loop.yaml")
    return Settings(**{k: v for k, v in defaults.items() if v is not None})


def get_constraint_rules() -> list[dict]:
    data = _load_yaml("constraints.yaml")
    return data.get("rules", [])


def get_objective_templates() -> dict:
    data = _load_yaml("objective_templates.yaml")
    return data.get("templates", {})
