"""Provider selection.

Returns the configured provider, or a safe stub when no LLM is configured so the
app still boots and the rest of the pipeline is testable.
"""

from datetime import date

from ..config import settings
from ..operations import OperationSet
from .base import LLMProvider


class StubProvider:
    """Used when no LLM is configured. The propose/preview/confirm pipeline still
    works for manual edits; this just reports that AI editing is unavailable."""

    def __init__(self, message: str | None = None) -> None:
        self.message = message or (
            "AI editing isn't configured. Set LLM_PROVIDER plus the matching "
            "API key in the backend environment to enable natural-language edits."
        )

    def propose_operations(
        self, course_state: dict, message: str, history: list[dict], today: date
    ) -> OperationSet:
        return OperationSet(
            explanation="",
            needs_clarification=self.message,
        )


def get_provider() -> LLMProvider:
    provider = settings.llm_provider.lower().strip()
    if provider in {"openai", "openai_compatible"}:
        if settings.openai_api_key or settings.openai_base_url:
            from .openai_provider import OpenAIProvider

            return OpenAIProvider()
        return StubProvider()

    if provider == "anthropic" and settings.anthropic_api_key:
        try:
            from .anthropic_provider import AnthropicProvider
        except ImportError:
            return StubProvider(
                "The Anthropic provider is configured, but the anthropic package "
                "is not installed. Switch LLM_PROVIDER to openai, or install the "
                "anthropic package if you still need Claude."
            )

        return AnthropicProvider()

    return StubProvider()
