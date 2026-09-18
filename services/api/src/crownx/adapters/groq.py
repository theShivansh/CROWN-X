"""GroqProvider: the production answer call (ADR-017) over Groq's OpenAI-compatible API.

Same system prompt, user turn and `submit_answer` tool as every other provider. The API key comes from
SSM Parameter Store in AWS (or GROQ_API_KEY locally) and is never logged or echoed.

Reliability layer, one ordered policy per request, inside a deadline that fits API Gateway's 30 s:
1. timeout: retry once with the same model;
2. 429: retry once with the same model only when `Retry-After` is 2 s or less (after waiting it);
3. anything else, or the retry failing too: fall back once to the fallback model;
4. the fallback failing as well: `AnswerUnavailable`.
Every attempt is recorded (model and outcome) so the audit and the logs say which model answered.
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
from crownx.domain.errors import AnswerUnavailable

# (url, headers, body, timeout) -> parsed JSON response. Injected so tests never touch the network.
Transport = Callable[[str, dict, bytes, float], dict]

MAX_RETRY_AFTER_S = 2.0
DEADLINE_S = 26.0  # API Gateway gives up at 30 s; leave room for the rest of the request
MIN_ATTEMPT_S = 2.0  # don't start a call with less time than this left


def urllib_transport(url: str, headers: dict, body: bytes, timeout: float) -> dict:
    request = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.URLError as error:
        # A connect or read timeout can surface wrapped in URLError; the policy needs to see it.
        if isinstance(error.reason, TimeoutError):
            raise TimeoutError(str(error.reason)) from error
        raise


class _Failed(Exception):
    """One attempt failed; `outcome` is what the audit records."""

    def __init__(self, outcome: str, retry_after: float | None = None) -> None:
        super().__init__(outcome)
        self.outcome = outcome
        self.retry_after = retry_after


class GroqAnswerer:
    provider = "groq"

    def __init__(
        self,
        api_key: str,
        model_id: str,
        base_url: str = "https://api.groq.com/openai/v1",
        transport: Transport = urllib_transport,
        timeout_s: float = 10.0,
        fallback_model_id: str | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        deadline_s: float = DEADLINE_S,
    ) -> None:
        self._api_key = api_key
        self.model_id = model_id
        self.fallback_model_id = fallback_model_id
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._transport = transport
        self._timeout = timeout_s
        self._sleep = sleep
        self._clock = clock
        self._deadline_s = deadline_s

    def request(self, question: str, evidence: list[dict], model_id: str | None = None) -> dict:
        model = model_id or self.model_id
        body: dict = {
            "model": model,
            "temperature": 0,
            "max_completion_tokens": 2048,
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
        if model.startswith("openai/gpt-oss"):
            # Reasoning models spend tokens thinking; low keeps the answer call fast and bounded.
            body["reasoning_effort"] = "low"
        return body

    def answer(self, question: str, evidence: list[dict]) -> AnswerResult:
        started = self._clock()
        deadline = started + self._deadline_s
        attempts: list[dict] = []
        models = [self.model_id]
        if self.fallback_model_id and self.fallback_model_id != self.model_id:
            models.append(self.fallback_model_id)

        for model in models:
            retried = False
            while True:
                try:
                    response, draft = self._attempt(question, evidence, model, deadline)
                except _Failed as failure:
                    attempts.append({"model_id": model, "outcome": failure.outcome})
                    if retried or failure.outcome == "deadline":
                        break
                    if failure.outcome == "timeout":
                        retried = True
                        continue
                    if (
                        failure.outcome == "rate_limited"
                        and failure.retry_after is not None
                        and failure.retry_after <= MAX_RETRY_AFTER_S
                        and self._clock() + failure.retry_after + MIN_ATTEMPT_S < deadline
                    ):
                        self._sleep(failure.retry_after)
                        retried = True
                        continue
                    break  # anything else: go to the fallback model
                else:
                    attempts.append({"model_id": model, "outcome": "ok"})
                    usage = response.get("usage") or {}
                    return AnswerResult(
                        draft=draft,
                        provider=self.provider,
                        model_id=model,
                        latency_ms=round((self._clock() - started) * 1000),
                        input_tokens=usage.get("prompt_tokens"),
                        output_tokens=usage.get("completion_tokens"),
                        invocation_id=response.get("id"),
                        attempts=tuple(attempts),
                    )
            if attempts[-1]["outcome"] == "deadline":
                break

        error = AnswerUnavailable(
            "The answer model is busy or unavailable right now, so no answer was written. "
            "The evidence panel still shows every retrieved passage; retry in a moment."
        )
        error.attempts = tuple(attempts)  # type: ignore[attr-defined]  # read by the audit
        raise error

    def _attempt(
        self, question: str, evidence: list[dict], model: str, deadline: float
    ) -> tuple[dict, AnswerDraft]:
        remaining = deadline - self._clock()
        if remaining < MIN_ATTEMPT_S:
            raise _Failed("deadline")
        body = json.dumps(self.request(question, evidence, model)).encode()
        headers = {"content-type": "application/json", "authorization": f"Bearer {self._api_key}"}
        try:
            response = self._transport(self._url, headers, body, min(self._timeout, remaining))
        except TimeoutError as error:
            raise _Failed("timeout") from error
        except urllib.error.HTTPError as error:
            if error.code == 429:
                raise _Failed("rate_limited", _retry_after(error)) from error
            raise _Failed(f"http_{error.code}") from error
        except (urllib.error.URLError, OSError) as error:
            raise _Failed("unreachable") from error
        return response, _draft_from(response)


def _retry_after(error: urllib.error.HTTPError) -> float | None:
    value = error.headers.get("retry-after") if error.headers is not None else None
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _draft_from(response: dict) -> AnswerDraft:
    for choice in response.get("choices") or []:
        for call in (choice.get("message") or {}).get("tool_calls") or []:
            function = call.get("function") or {}
            if function.get("name") == TOOL_NAME:
                try:
                    return AnswerDraft.model_validate(json.loads(function.get("arguments") or "{}"))
                except (ValidationError, json.JSONDecodeError) as error:
                    raise _Failed("wrong_format") from error
    raise _Failed("no_tool_call")
