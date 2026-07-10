from __future__ import annotations

from gcl.domain.contracts import Evidence


class SignalSource:
    def measure(self) -> list[Evidence]:
        raise NotImplementedError


class FixtureSignalSource(SignalSource):
    def __init__(self, evidence: list[Evidence]):
        self._evidence = evidence

    def measure(self) -> list[Evidence]:
        return list(self._evidence)
