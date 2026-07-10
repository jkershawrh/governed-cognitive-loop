from enum import Enum


class ConstraintType(str, Enum):
    CAPACITY = "capacity"
    PRIORITY = "priority"
    COMPLIANCE = "compliance"
    RESIDENCY = "residency"
    BUDGET = "budget"
    LATENCY = "latency"
    CUSTOM = "custom"


class Verdict(str, Enum):
    SURVIVES = "survives"
    FAILS = "fails"


class ConstraintSource(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"
    CLASSIFICATION = "classification"
