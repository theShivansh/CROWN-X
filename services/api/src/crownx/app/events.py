"""Writing workflow events (ADR-018) without letting observability break the product path."""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime, timedelta

from crownx.adapters.ports import MetadataStore
from crownx.domain.events import EventType, WorkflowEvent, new_event_id

log = logging.getLogger(__name__)

_lock = threading.Lock()
_last: datetime | None = None


def event_time() -> str:
    """UTC now, strictly increasing within this process. Some clocks (Windows) tick in milliseconds,
    and two events of one request must keep the order they happened in."""
    global _last
    with _lock:
        now = datetime.now(UTC)
        if _last is not None and now <= _last:
            now = _last + timedelta(microseconds=1)
        _last = now
    return now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def record_event(
    store: MetadataStore, workspace_id: str, event_type: EventType, **attributes: object
) -> None:
    """Append one event. A failure is logged and swallowed: the request it describes still succeeds."""
    try:
        store.put_event(
            WorkflowEvent(
                event_id=new_event_id(),
                workspace_id=workspace_id,
                event_type=event_type,
                occurred_at=event_time(),
                attributes=attributes,
            )
        )
    except Exception:  # noqa: BLE001
        log.warning("workflow event %s not recorded", event_type.value, exc_info=True)
