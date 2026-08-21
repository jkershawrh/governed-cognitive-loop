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


class AdversaryStatus(str, Enum):
    """Whether the LLM adversarial probe ran, and if not, why.

    Recorded on every FalsificationResult so a SURVIVES verdict states which
    gates actually executed rather than leaving it to be inferred.
    """

    PROBED = "probed"
    """The adversary ran and raised no objection."""

    OBJECTED = "objected"
    """The adversary ran and falsified the action."""

    SKIPPED_RULES_MODE = "skipped_rules_mode"
    """Deterministic rules mode was forced, so no LLM was consulted."""

    UNAVAILABLE = "unavailable"
    """No inference endpoint configured, or the response was unusable."""

    NOT_REACHED = "not_reached"
    """A deterministic check failed first, so the adversary was never called."""


class ConstraintSource(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"
    CLASSIFICATION = "classification"
