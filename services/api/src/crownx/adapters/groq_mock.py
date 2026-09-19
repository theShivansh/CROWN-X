"""MockGroqTransport: Groq's chat-completions API, scripted, with no network (ADR-017).

It sits under the real `GroqAnswerer`, so tests and the offline evaluation exercise the production
adapter (request building, tool-call parsing, the retry and fallback policy, then `finalize()`) without
spending Groq's rate limit or failing on a 429. Allowed in `development` and `test` only; config.py
refuses it in production.

Answers are extractive (the `MockAnswerer` rule over the evidence found in the request) and cite only
IDs present in the request, unless a mode says otherwise. They measure the pipeline, never model
quality.

A mode is a script of outcomes consumed one per call; once it runs out every call succeeds.
"""

from __future__ import annotations

import email.message
import html
import io
import json
import re
import urllib.error

from crownx.adapters.mock import MockAnswerer
from crownx.adapters.prompting import TOOL_NAME

_EVIDENCE = re.compile(r'<evidence id="([^"]*)"[^>]*>\n(.*?)\n</evidence>', re.DOTALL)
_QUESTION = re.compile(r"\AQuestion: (.*?)\n\n", re.DOTALL)

# Outcomes: "ok", "invented_id", "malformed_json", "no_tool_call", "timeout", "http_500",
# "rate_limited:<seconds>" (a 429 carrying that Retry-After).
MODES: dict[str, list[str]] = {
    "ok": [],
    "invented_id": ["invented_id"],
    "malformed_json": ["malformed_json", "malformed_json"],
    "no_tool_call": ["no_tool_call", "no_tool_call"],
    "rate_limited": ["rate_limited:1"],  # short wait: same model retries and answers
    "rate_limited_long": ["rate_limited:30"],  # long wait: the fallback model answers
    "timeout": ["timeout"],  # one timeout: the same model retries and answers
    "timeout_twice": ["timeout", "timeout"],  # the fallback model answers
    "fallback_ok": ["http_500"],  # primary fails once: the fallback model answers
    "all_fail": ["rate_limited:30", "http_500"],  # primary and fallback both fail
}


class MockGroqTransport:
    def __init__(self, mode: str = "ok") -> None:
        if mode not in MODES:
            raise ValueError(f"unknown mock mode {mode!r}; choose one of {sorted(MODES)}")
        self._script = list(MODES[mode])
        self.calls: list[dict] = []  # each request body, parsed, for assertions

    def __call__(self, url: str, headers: dict, body: bytes, timeout: float) -> dict:
        request = json.loads(body)
        self.calls.append(request)
        outcome = self._script.pop(0) if self._script else "ok"
        if outcome == "timeout":
            raise TimeoutError("mock timeout")
        if outcome == "http_500":
            raise _http_error(url, 500, {})
        if outcome.startswith("rate_limited:"):
            raise _http_error(url, 429, {"retry-after": outcome.split(":", 1)[1]})
        if _tool_of(request) == "name_workflow":
            return _named(request)
        return _completion(request, outcome)


def _http_error(url: str, code: int, headers: dict) -> urllib.error.HTTPError:
    message = email.message.Message()
    for key, value in headers.items():
        message[key] = value
    return urllib.error.HTTPError(url, code, "mock", message, io.BytesIO(b"{}"))


def _completion(request: dict, outcome: str) -> dict:
    user = next(m["content"] for m in request["messages"] if m["role"] == "user")
    question_match = _QUESTION.search(user)
    question = question_match.group(1) if question_match else ""
    evidence = [
        {"evidence_id": html.unescape(eid), "quoted_span": html.unescape(body)}
        for eid, body in _EVIDENCE.findall(user)
    ]
    draft = MockAnswerer().answer(question, evidence).draft.model_dump()
    if outcome == "invented_id":
        draft["claims"].append({"text": "An invented fact.", "evidence_ids": ["ev_999"]})
    arguments = "{not json" if outcome == "malformed_json" else json.dumps(draft)
    message: dict = {"role": "assistant", "content": None}
    if outcome != "no_tool_call":
        message["tool_calls"] = [
            {
                "id": "call_mock",
                "type": "function",
                "function": {"name": TOOL_NAME, "arguments": arguments},
            }
        ]
    else:
        message["content"] = "Here is a free-text answer instead of the tool."
    return {
        "id": f"chatcmpl-mock-{len(evidence)}",
        "model": request["model"],
        "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls"}],
        "usage": {"prompt_tokens": len(user) // 4, "completion_tokens": len(arguments) // 4},
    }


def _tool_of(request: dict) -> str | None:
    tools = request.get("tools") or []
    return (tools[0].get("function") or {}).get("name") if tools else None


def _named(request: dict) -> dict:
    """A deterministic name for a naming request: the first and last step it was given."""
    user = next(m["content"] for m in request["messages"] if m["role"] == "user")
    steps = user.splitlines()[0].removeprefix("Steps, in order: ").split(" -> ")
    arguments = json.dumps(
        {
            "name": f"{steps[0]} to {steps[-1]}".replace("_", " ")[:40],
            "description": f"The team repeats {len(steps)} steps in this order.",
        }
    )
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_mock",
                "type": "function",
                "function": {"name": "name_workflow", "arguments": arguments},
            }
        ],
    }
    return {
        "id": "chatcmpl-mock-name",
        "model": request["model"],
        "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls"}],
        "usage": {"prompt_tokens": len(user) // 4, "completion_tokens": len(arguments) // 4},
    }
