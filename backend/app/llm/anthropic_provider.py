"""Legacy Claude-backed provider.

This remains available for projects that still configure LLM_PROVIDER=anthropic,
but OpenAI is now the default provider.
"""

from datetime import date

import anthropic

from ..config import settings
from ..operations import OperationSet
from .prompt import system_prompt, user_content

_TOOL = {
    "name": "submit_changes",
    "description": "Submit the structured edits to apply to the syllabus, "
    "or a clarifying question if the request is ambiguous.",
    "input_schema": OperationSet.model_json_schema(),
}


class AnthropicProvider:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.llm_model

    def propose_operations(
        self, course_state: dict, message: str, history: list[dict], today: date
    ) -> OperationSet:
        system = [
            {
                "type": "text",
                "text": system_prompt(today),
                "cache_control": {"type": "ephemeral"},
            }
        ]
        messages = [
            *[{"role": m["role"], "content": m["content"]} for m in history],
            {"role": "user", "content": user_content(course_state, message)},
        ]

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=system,
            tools=[_TOOL],
            messages=messages,
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_changes":
                return OperationSet.model_validate(block.input)

        # No tool call — surface any text the model returned as a clarification.
        text = " ".join(b.text for b in response.content if b.type == "text").strip()
        return OperationSet(
            needs_clarification=text or "I couldn't determine a concrete change. Could you rephrase?"
        )
