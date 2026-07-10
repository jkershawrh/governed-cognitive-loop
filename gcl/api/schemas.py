from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from gcl.domain.contracts import LoopCycle


class SignalInput(BaseModel):
    metric: str
    value: float
    source: str = "api"


class CycleRequest(BaseModel):
    signals: list[SignalInput]


class CycleResponse(BaseModel):
    cycle_id: str
    correlation_id: str
    committed: bool
    action_type: Optional[str] = None
    falsification_verdict: Optional[str] = None


class CycleDetail(BaseModel):
    cycle: LoopCycle


class ChainEntry(BaseModel):
    entry_id: str
    entry_type: str
    correlation_id: str
    content: dict
