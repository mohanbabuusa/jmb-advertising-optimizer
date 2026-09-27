from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: Literal["SET_WEEKLY_BUDGET"]
    proposedWeeklyBudgetCents: int = Field(ge=0, le=10000000)
    reasoning: str = Field(min_length=1, max_length=4000)
    assumptions: list[str] = Field(max_length=10)


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    decision: Literal["APPROVE", "REJECT"]
    expectedVersion: int = Field(ge=1)
    proposalHash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    comment: str = Field(default="", max_length=1000)


class EmptyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
