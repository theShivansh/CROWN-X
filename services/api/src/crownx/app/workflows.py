"""Workflow Learning Lite, the M5 half (FR-WL-01..08; ADR-005, ADR-018, ADR-022).

Behind `WORKFLOWS_ENABLED`: with it off, every method raises `NotFound`, so each route is a 404 and
nothing is written. Suggestions only. Nothing here runs a workflow.

- Client events: what the user does in the UI. They're ordered by the time the server received
  them, like the server's own events, so one clock orders every step; the browser's time is kept
  as `client_at`. A retry is recognised by the browser's UUIDv7 `event_id` and stored once.
- Suggestions: mined from the events whenever they're read (`domain/workflow.mine`, deterministic),
  merged with what's stored about each one: its name, and whether it was dismissed.
- Refresh: mines, and names each new suggestion once with the model (given step types and relative
  times only). A failed call keeps the rule name; nothing depends on the model's text.
- Save: an immutable, versioned template. Dismiss: hidden until its support grows past today's.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from crownx.adapters.ports import MetadataStore
from crownx.app.events import event_time, record_event
from crownx.domain.errors import InvalidRequest, LimitReached, NotFound
from crownx.domain.events import CLIENT_EVENT_TYPES, EventType, WorkflowEvent
from crownx.domain.models import utc_now
from crownx.domain.workflow import DEFINITIONS, MinerConfig, WorkflowSuggestion, mine

log = logging.getLogger(__name__)

# (steps, example traces as "step +Ns" lists) -> (name, description, model) or None
Namer = Callable[[list[str], list[list[str]]], tuple[str, str, str] | None]

UUID7 = r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
REF_KEYS = {"evidence_id", "conflict_id", "query_id", "key", "suggestion_id"}
_REF_VALUE = re.compile(r"^[A-Za-z0-9_:/.=-]{1,80}$")
MAX_NAMES_PER_REFRESH = 3


class ClientEvent(BaseModel):
    """`POST /workspaces/{ws}/events`. IDs only: no text can be stored through this route."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(pattern=UUID7)
    event_type: EventType
    occurred_at: datetime
    ref: dict[str, str] = Field(default_factory=dict, max_length=5)

    @field_validator("event_type")
    @classmethod
    def _client_type(cls, value: EventType) -> EventType:
        if value not in CLIENT_EVENT_TYPES:
            raise ValueError("this event type is recorded by the server")
        return value

    @field_validator("ref")
    @classmethod
    def _ids_only(cls, value: dict[str, str]) -> dict[str, str]:
        for key, item in value.items():
            if key not in REF_KEYS or not _REF_VALUE.match(item):
                raise ValueError(f"ref may hold only IDs ({', '.join(sorted(REF_KEYS))})")
        return value


class SaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=3, max_length=40, pattern=r"^[^<>\n\r]+$")


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _examples(suggestion: WorkflowSuggestion) -> list[list[str]]:
    """Two traces as step types with seconds since the trace began: no IDs, no text."""
    examples = []
    for times in suggestion.trace_times[-2:]:
        start = datetime.fromisoformat(times[0].replace("Z", "+00:00"))
        examples.append(
            [
                f"{step} +{round((datetime.fromisoformat(t.replace('Z', '+00:00')) - start).total_seconds())}s"
                for step, t in zip(suggestion.steps, times, strict=True)
            ]
        )
    return examples


class Workflows:
    def __init__(
        self,
        store: MetadataStore,
        require_workspace: Callable[[str], object],
        enabled: bool,
        config: MinerConfig,
        namer: Namer | None = None,
        events_per_hour: int = 600,
    ) -> None:
        self._store = store
        self._require_workspace = require_workspace
        self.enabled = enabled
        self._config = config
        self._namer = namer
        self._events_per_hour = events_per_hour

    def _guard(self, workspace_id: str) -> None:
        if not self.enabled:
            raise NotFound("Not found.")
        self._require_workspace(workspace_id)

    # Events -------------------------------------------------------------------------------------

    def record(self, workspace_id: str, body: dict) -> WorkflowEvent:
        self._guard(workspace_id)
        try:
            event = ClientEvent.model_validate(body)
        except ValidationError as error:
            fields = sorted({".".join(str(p) for p in e["loc"]) or "body" for e in error.errors()})
            raise InvalidRequest(f"Check these fields: {', '.join(fields)}.") from error
        at = (
            event.occurred_at if event.occurred_at.tzinfo else event.occurred_at.replace(tzinfo=UTC)
        )
        stored = WorkflowEvent(
            event_id=event.event_id,
            workspace_id=workspace_id,
            event_type=event.event_type,
            occurred_at=event_time(),  # the server's clock orders every step
            attributes={"source": "client", "client_at": _stamp(at), **event.ref},
        )
        if not self._store.claim_event_id(workspace_id, event.event_id):
            return stored  # a retry: already recorded, and not counted again
        self._spend(workspace_id, datetime.now(UTC))
        self._store.put_event(stored)
        return stored

    def _spend(self, workspace_id: str, now: datetime) -> None:
        window = now.strftime("%Y-%m-%dT%H")
        expires_at = int(now.replace(minute=0, second=0, microsecond=0).timestamp()) + 2 * 3600
        if (
            self._store.count_usage(workspace_id, "events", window, expires_at)
            > self._events_per_hour
        ):
            raise LimitReached(
                f"This workspace has sent {self._events_per_hour} events this hour. "
                "Suggestions keep working; new actions count again next hour."
            )

    # Suggestions --------------------------------------------------------------------------------

    def suggestions(self, workspace_id: str) -> dict:
        self._guard(workspace_id)
        return self._view(workspace_id, mine(self._store.list_events(workspace_id), self._config))

    def refresh(self, workspace_id: str) -> dict:
        """Mine now, and name up to three suggestions that have no name yet (one model call each)."""
        self._guard(workspace_id)
        mined = mine(self._store.list_events(workspace_id), self._config)
        states = self._store.get_workflow_states(workspace_id)
        named = 0
        for suggestion in mined:
            if suggestion.suggestion_id in states:
                continue
            state = {
                "name": suggestion.name,
                "description": None,
                "named_by": "rule",
                "first_seen": utc_now(),
                "dismissed_at_support": None,
            }
            if self._namer is not None and named < MAX_NAMES_PER_REFRESH:
                named += 1
                result = None
                try:
                    result = self._namer(suggestion.steps, _examples(suggestion))
                except Exception:  # noqa: BLE001 - naming is decoration; never fail the refresh
                    log.warning("workflow naming failed", exc_info=True)
                if result is not None:
                    state["name"], state["description"], state["named_by"] = result
            self._store.put_workflow_state(workspace_id, suggestion.suggestion_id, state)
            states[suggestion.suggestion_id] = state
        return self._view(workspace_id, mined, states)

    def save(self, workspace_id: str, suggestion_id: str, body: dict | None) -> dict:
        self._guard(workspace_id)
        try:
            request = SaveRequest.model_validate(body or {})
        except ValidationError as error:
            raise InvalidRequest("A workflow name is 3 to 40 characters, on one line.") from error
        suggestion = self._current(workspace_id, suggestion_id)
        state = self._store.get_workflow_states(workspace_id).get(suggestion_id) or {}
        template = {
            "suggestion_id": suggestion_id,
            "name": request.name or state.get("name") or suggestion.name,
            "description": state.get("description"),
            "steps": suggestion.steps,
            "support": suggestion.support,
            "source_event_ids": suggestion.traces[-1],
            "saved_at": utc_now(),
            "automation": "none",
        }
        template["version"] = self._store.add_template(workspace_id, suggestion_id, template)
        record_event(
            self._store,
            workspace_id,
            EventType.WORKFLOW_SAVED,
            suggestion_id=suggestion_id,
            version=template["version"],
        )
        return template

    def dismiss(self, workspace_id: str, suggestion_id: str) -> None:
        self._guard(workspace_id)
        suggestion = self._current(workspace_id, suggestion_id)
        state = self._store.get_workflow_states(workspace_id).get(suggestion_id) or {
            "name": suggestion.name,
            "description": None,
            "named_by": "rule",
            "first_seen": utc_now(),
        }
        self._store.put_workflow_state(
            workspace_id, suggestion_id, {**state, "dismissed_at_support": suggestion.support}
        )

    def _current(self, workspace_id: str, suggestion_id: str) -> WorkflowSuggestion:
        for suggestion in mine(self._store.list_events(workspace_id), self._config):
            if suggestion.suggestion_id == suggestion_id:
                return suggestion
        raise NotFound("Workflow suggestion not found in this workspace.")

    def _view(
        self,
        workspace_id: str,
        mined: list[WorkflowSuggestion],
        states: dict[str, dict] | None = None,
    ) -> dict:
        states = states if states is not None else self._store.get_workflow_states(workspace_id)
        templates = self._store.list_templates(workspace_id)
        shown = []
        for suggestion in mined:
            state = states.get(suggestion.suggestion_id) or {}
            dismissed = state.get("dismissed_at_support")
            if dismissed is not None and suggestion.support <= int(dismissed):
                continue  # hidden until it happens again
            versions = sorted(
                (t for t in templates if t["suggestion_id"] == suggestion.suggestion_id),
                key=lambda t: t["version"],
            )
            shown.append(
                {
                    **suggestion.model_dump(mode="json"),
                    "rule_name": suggestion.name,
                    "name": state.get("name") or suggestion.name,
                    "description": state.get("description"),
                    "named_by": state.get("named_by", "rule"),
                    "saved_versions": [
                        {"version": t["version"], "name": t["name"], "saved_at": t["saved_at"]}
                        for t in versions
                    ],
                }
            )
        return {
            "suggestions": shown,
            "templates": sorted(templates, key=lambda t: (t["saved_at"], t["version"])),
            "definitions": DEFINITIONS,
            "automation": "none",
        }
