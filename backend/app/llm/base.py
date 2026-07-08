"""The single seam every LLM provider implements. Callers depend only on this —
swapping providers is a one-file change."""

from datetime import date
from typing import Protocol

from ..operations import OperationSet


class LLMProvider(Protocol):
    def propose_operations(
        self,
        course_state: dict,
        message: str,
        history: list[dict],
        today: date,
    ) -> OperationSet:
        """Translate a natural-language instruction into a typed OperationSet.

        Must never mutate data or call the database — it only proposes."""
        ...
