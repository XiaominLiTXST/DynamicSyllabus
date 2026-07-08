"""OpenAI and OpenAI-compatible provider.

The official OpenAI path uses the Responses API. For providers that expose an
OpenAI-compatible Chat Completions endpoint, set LLM_ENDPOINT=chat and
OPENAI_BASE_URL to that provider's base URL.
"""

import json
from datetime import date

from openai import OpenAI

from ..config import settings
from ..operations import OperationSet
from .prompt import system_prompt, user_content


def _schema_format() -> dict:
    return {
        "type": "json_schema",
        "name": "operation_set",
        "schema": OperationSet.model_json_schema(),
        # Keep this false because Pydantic's discriminated union schema is richer
        # than the strict subset some providers accept, while we still validate
        # with Pydantic before any DB change.
        "strict": False,
    }


def _chat_response_format() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "operation_set",
            "schema": OperationSet.model_json_schema(),
            "strict": False,
        },
    }


class OpenAIProvider:
    def __init__(self) -> None:
        client_kwargs = {"api_key": settings.openai_api_key or "not-needed"}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        self.client = OpenAI(**client_kwargs)
        self.model = settings.llm_model
        self.endpoint = settings.llm_endpoint

    def propose_operations(
        self, course_state: dict, message: str, history: list[dict], today: date
    ) -> OperationSet:
        if self.endpoint == "chat":
            return self._chat_completions(course_state, message, history, today)
        return self._responses(course_state, message, history, today)

    def _responses(
        self, course_state: dict, message: str, history: list[dict], today: date
    ) -> OperationSet:
        input_messages = [
            *[
                {"role": m["role"], "content": m["content"]}
                for m in history
                if m.get("role") in {"user", "assistant"}
            ],
            {"role": "user", "content": user_content(course_state, message)},
        ]
        response = self.client.responses.create(
            model=self.model,
            instructions=system_prompt(today),
            input=input_messages,
            max_output_tokens=4096,
            text={"format": _schema_format()},
        )
        return OperationSet.model_validate_json(response.output_text)

    def _chat_completions(
        self, course_state: dict, message: str, history: list[dict], today: date
    ) -> OperationSet:
        messages = [
            {"role": "system", "content": system_prompt(today)},
            *[
                {"role": m["role"], "content": m["content"]}
                for m in history
                if m.get("role") in {"user", "assistant"}
            ],
            {"role": "user", "content": user_content(course_state, message)},
        ]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=4096,
            response_format=_chat_response_format(),
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("The model returned an empty response.")
        return OperationSet.model_validate(json.loads(content))
