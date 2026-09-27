from typing import Protocol


class ReasoningService(Protocol):
    """Proposal-only port. A future Bedrock adapter can implement this interface."""

    def recommend(self, context: dict) -> dict: ...
