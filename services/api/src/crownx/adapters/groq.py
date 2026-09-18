"""GroqProvider: the answer call over Groq's OpenAI-compatible API, for development and tests only.

Never allowed in production (config.py, ADR-016). The API key comes from GROQ_API_KEY in the
environment and is never logged. Same system prompt, user turn and tool as Bedrock.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable

from pydantic import ValidationError

from crownx.adapters.ports import AnswerResult
from crownx.adapters.prompting import (
    SUBMIT_ANSWER_SCHEMA,
    TOOL_DESCRIPTION,
    TOOL_NAME,
    system_prompt,
    user_message,
)
from crownx.domain.answering import AnswerDraft
from crownx.domain.errors import AnswerUnavailable, ModelTimeout

# (url, headers, body, timeout) -> parsed JSON response. Injected so tests never touch the network.
Transport = Callable[[str, dict, bytes, float], dict]


def _urllib_transport(url: str, headers: dict, body: bytes, timeout: float) -> dict:
    request = urllib.request.Request(url, data=body, method="POST", headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


class GroqAnswerer:
    provider = "groq"

    def __init__(
        self,
        api_key: str,
        model_id: str,
        base_url: str = "https://api.groq.com/openai/v1",
        transport: Transport = _urllib_transport,
        timeout_s: float = 12.0,
    ) -> None:
        self._api_key = api_key
        self.model_id = model_id
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._transport = transport
        self._timeout = timeout_s

    def request(self, question: str, evidence: list[dict]) -> dict:
        return {
            "model": self.model_id,
            "temperature": 0,
            "max_tokens": 1024,
            "messages": [
                {"role": "system", "content": system_prompt()},
                {"role": "user", "content": user_message(question, evidence)},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": TOOL_NAME,
                        "description": TOOL_DESCRIPTION,
                        "parameters": SUBMIT_ANSWER_SCHEMA,
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
        }

    def answer(self, question: str, evidence: list[dict]) -> AnswerResult:
        body = json.dumps(self.request(question, evidence)).encode()
        headers = {"content-type": "application/json", "authorization": f"Bearer {self._api_key}"}
        started = time.perf_counter()
        response = self._call_with_one_retry(headers, body)
        usage = response.get("usage") or {}
        return AnswerResult(
            draft=_draft_from(response),
            provider=self.provider,
            model_id=self.model_id,
            latency_ms=round((time.perf_counter() - started) * 1000),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            invocation_id=response.get("id"),
        )

    def _call_with_one_retry(self, headers: dict, body: bytes) -> dict:
        for attempt in (1, 2):
            try:
                return self._transport(self._url, headers, body, self._timeout)
            except TimeoutError as error:
                if attempt == 2:
                    raise ModelTimeout(
                        "The answer model didn't respond in time. Retry in a moment."
                    ) from error
            except urllib.error.HTTPError as error:
                if error.code in (429, 503) and attempt == 1:
                    continue
                raise AnswerUnavailable(
                    "The answer model refused the request, so no answer was written."
                ) from error
        raise AssertionError("unreachable")


def _draft_from(response: dict) -> AnswerDraft:
    for choice in response.get("choices") or []:
        for call in (choice.get("message") or {}).get("tool_calls") or []:
            function = call.get("function") or {}
            if function.get("name") == TOOL_NAME:
                try:
                    return AnswerDraft.model_validate(json.loads(function.get("arguments") or "{}"))
                except (ValidationError, json.JSONDecodeError) as error:
                    raise AnswerUnavailable(
                        "The answer model replied in the wrong format, so no answer was written."
                    ) from error
    raise AnswerUnavailable(
        "The answer model didn't use the answer format, so no answer was written."
    )
