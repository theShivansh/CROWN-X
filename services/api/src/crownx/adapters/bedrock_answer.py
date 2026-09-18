"""BedrockProvider's answer call: one Converse request with the `submit_answer` tool (M2 prompt §4).

The embedding half of BedrockProvider is `adapters/bedrock.py` (TitanEmbedder), unchanged. The model ID
comes from config (ADR-013 is still proposed, so it's a candidate, never a literal here).
"""

from __future__ import annotations

import time
from typing import Any

from botocore.exceptions import ClientError, ConnectTimeoutError, ReadTimeoutError
from pydantic import ValidationError

from crownx.adapters.ports import AnswerResult
from crownx.adapters.prompting import (
    AUTO_TOOL_INSTRUCTION,
    SUBMIT_ANSWER_SCHEMA,
    TOOL_DESCRIPTION,
    TOOL_NAME,
    system_prompt,
    user_message,
)
from crownx.domain.answering import AnswerDraft
from crownx.domain.errors import AnswerUnavailable, ModelTimeout

# Worth one retry: the call is idempotent and these usually clear within seconds.
_TRANSIENT = {"ThrottlingException", "ServiceUnavailableException", "ModelNotReadyException"}


class ConverseAnswerer:
    provider = "bedrock"

    def __init__(
        self, client: Any, model_id: str, force_tool: bool = True, max_tokens: int = 1024
    ) -> None:
        self._client = client  # bedrock-runtime, with short read timeouts and SDK retries off
        self.model_id = model_id
        self._force_tool = force_tool
        self._max_tokens = max_tokens

    def request(self, question: str, evidence: list[dict]) -> dict:
        text = user_message(question, evidence)
        if not self._force_tool:
            text = f"{text}\n\n{AUTO_TOOL_INSTRUCTION}"
        return {
            "modelId": self.model_id,
            "system": [{"text": system_prompt()}],
            "messages": [{"role": "user", "content": [{"text": text}]}],
            "toolConfig": {
                "tools": [
                    {
                        "toolSpec": {
                            "name": TOOL_NAME,
                            "description": TOOL_DESCRIPTION,
                            "inputSchema": {"json": SUBMIT_ANSWER_SCHEMA},
                        }
                    }
                ],
                "toolChoice": {"tool": {"name": TOOL_NAME}} if self._force_tool else {"auto": {}},
            },
            "inferenceConfig": {"maxTokens": self._max_tokens, "temperature": 0},
        }

    def answer(self, question: str, evidence: list[dict]) -> AnswerResult:
        request = self.request(question, evidence)
        started = time.perf_counter()
        response = self._call_with_one_retry(request)
        latency_ms = round((time.perf_counter() - started) * 1000)
        usage = response.get("usage") or {}
        return AnswerResult(
            draft=_draft_from(response),
            provider=self.provider,
            model_id=self.model_id,
            latency_ms=latency_ms,
            input_tokens=usage.get("inputTokens"),
            output_tokens=usage.get("outputTokens"),
            invocation_id=(response.get("ResponseMetadata") or {}).get("RequestId"),
        )

    def _call_with_one_retry(self, request: dict) -> dict:
        for attempt in (1, 2):
            try:
                return self._client.converse(**request)
            except (ReadTimeoutError, ConnectTimeoutError) as error:
                if attempt == 2:
                    raise ModelTimeout(
                        "The answer model didn't respond in time. Retry in a moment."
                    ) from error
            except ClientError as error:
                code = error.response.get("Error", {}).get("Code", "")
                if code in _TRANSIENT and attempt == 1:
                    continue
                raise AnswerUnavailable(
                    "The answer model refused the request, so no answer was written. "
                    "The evidence panel still shows every retrieved passage."
                ) from error
        raise AssertionError("unreachable")


def _draft_from(response: dict) -> AnswerDraft:
    content = ((response.get("output") or {}).get("message") or {}).get("content") or []
    for block in content:
        tool_use = block.get("toolUse")
        if tool_use and tool_use.get("name") == TOOL_NAME:
            try:
                return AnswerDraft.model_validate(tool_use.get("input") or {})
            except ValidationError as error:
                raise AnswerUnavailable(
                    "The answer model replied in the wrong format, so no answer was written. Retry."
                ) from error
    raise AnswerUnavailable(
        "The answer model didn't use the answer format, so no answer was written. Retry."
    )
