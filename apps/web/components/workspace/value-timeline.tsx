"use client";

import { ArrowCounterClockwise, CheckCircle, GitDiff, X } from "@phosphor-icons/react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { ErrorNotice } from "@/components/error-notice";
import { Skeleton } from "@/components/ui/skeleton";
import { api, asApiError, type ApiError, type Evidence, type Timeline } from "@/lib/api";
import { conflictSegments, eventDate, eventValue, nextIndex, timelineRule, timelineSummary } from "@/lib/timeline";
import { cn } from "@/lib/utils";

export const TIMELINE_ELEMENT_ID = "value-timeline";

type Load = { state: "loading" } | { state: "error"; error: ApiError } | { state: "ready"; timeline: Timeline };

/**
 * UI_UX §3.6: one fact's value across every source, ordered by the selection rule's own signals.
 * A horizontal track when its own column is wide enough (a container query, since the three panes
 * leave the centre narrow at 1024px) and a vertical list otherwise; arrow keys step through the events.
 */
export function ValueTimeline(props: {
  workspaceId: string;
  factKey: string;
  label: string;
  evidence: Evidence[];
  onOpen: (evidenceId: string) => void;
  onClose: () => void;
}) {
  const { workspaceId, factKey, label, evidence, onOpen, onClose } = props;
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    const [subject, attribute] = factKey.split("/");
    api
      .timeline(workspaceId, subject, attribute)
      .then((timeline) => live && setLoad({ state: "ready", timeline }))
      .catch((error) => live && setLoad({ state: "error", error: asApiError(error) }));
    return () => {
      live = false;
    };
  }, [workspaceId, factKey, attempt]);

  return (
    <section
      id={TIMELINE_ELEMENT_ID}
      tabIndex={-1}
      aria-labelledby="timeline-heading"
      className="@container flex scroll-mt-4 flex-col gap-3 rounded-md border border-border bg-surface p-4 focus-visible:outline-none"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <h2 id="timeline-heading" className="text-sm font-medium text-text">
            Timeline · {label}
          </h2>
          {load.state === "ready" ? (
            <p className="text-xs text-text-muted">{timelineSummary(load.timeline)}</p>
          ) : null}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close the timeline"
          className="inline-flex size-7 shrink-0 items-center justify-center rounded-sm text-text-muted transition-colors duration-(--duration-fast) ease-out hover:bg-surface-3 hover:text-text focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <X className="size-4" aria-hidden />
        </button>
      </div>

      {load.state === "loading" ? (
        <div className="flex flex-col gap-2 @2xl:flex-row" aria-busy>
          <span className="sr-only">Loading the timeline for {label}</span>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24 flex-1 rounded-sm bg-surface-2" />
          ))}
        </div>
      ) : load.state === "error" ? (
        <ErrorNotice
          error={load.error}
          action={
            <button
              type="button"
              onClick={() => {
                setLoad({ state: "loading" });
                setAttempt((n) => n + 1);
              }}
              className="inline-flex items-center gap-1 rounded-sm text-sm text-accent underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              <ArrowCounterClockwise className="size-4" aria-hidden />
              Retry
            </button>
          }
        />
      ) : load.timeline.events.length === 0 ? (
        <p className="text-sm text-text-muted">No source in this workspace states the {label} yet.</p>
      ) : (
        <Track timeline={load.timeline} evidence={evidence} onOpen={onOpen} />
      )}
    </section>
  );
}

function Track(props: { timeline: Timeline; evidence: Evidence[]; onOpen: (evidenceId: string) => void }) {
  const { timeline, evidence, onOpen } = props;
  const { events } = timeline;
  const segments = conflictSegments(events);
  const [active, setActive] = useState(Math.max(events.length - 1, 0));
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(event: KeyboardEvent) {
    const next = nextIndex(event.key, active, events.length);
    if (next === null) return;
    event.preventDefault();
    setActive(next);
    buttons.current[next]?.focus();
  }

  return (
    <div className="flex flex-col gap-3">
      <ol
        aria-label={`How the ${timeline.label} changed, oldest first`}
        onKeyDown={onKeyDown}
        className="flex flex-col @2xl:flex-row @2xl:items-stretch"
      >
        {events.map((event, index) => {
          const passage = evidence.find((e) => e.chunk_id === event.source_chunk_id);
          const conflicted = segments[index];
          const value = eventValue(timeline, event);
          return (
            <li key={event.claim_id} className="flex flex-col @2xl:min-w-0 @2xl:flex-1 @2xl:flex-row @2xl:items-center">
              {index > 0 ? (
                <span
                  aria-hidden
                  className={cn(
                    "ml-5 h-5 w-0 shrink-0 border-l @2xl:mx-0 @2xl:h-0 @2xl:w-auto @2xl:min-w-6 @2xl:flex-1 @2xl:border-l-0 @2xl:border-t",
                    conflicted ? "border-dashed border-conflict @2xl:border-t-2" : "border-border-strong",
                  )}
                />
              ) : null}
              <button
                ref={(el) => {
                  buttons.current[index] = el;
                }}
                type="button"
                tabIndex={index === active ? 0 : -1}
                aria-disabled={!passage}
                onFocus={() => setActive(index)}
                onClick={() => passage && onOpen(passage.evidence_id)}
                aria-label={[
                  eventDate(event),
                  event.filename,
                  value,
                  event.changed ? "value changed" : index > 0 ? "no change" : "first source",
                  conflicted ? "conflicts with the previous source" : null,
                  event.selected ? "current value" : null,
                  passage ? "opens the passage" : "passage not among the retrieved evidence",
                ]
                  .filter(Boolean)
                  .join(", ")}
                className={cn(
                  "flex w-full min-w-0 flex-col items-start gap-1 rounded-sm border px-3 py-2.5 text-left transition-colors duration-(--duration-fast) ease-out focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none @2xl:w-44 @2xl:shrink-0",
                  event.selected
                    ? "border-accent bg-accent-soft"
                    : conflicted
                      ? "border-conflict bg-surface-2"
                      : "border-border bg-surface-2",
                  passage ? "hover:bg-surface-3" : "cursor-default",
                )}
              >
                <span className="font-mono text-xs tabular-nums text-text-muted">{eventDate(event)}</span>
                <span className="w-full truncate text-xs text-text-subtle" title={event.filename}>
                  {event.filename}
                  {event.version_label ? ` · ${event.version_label}` : ""}
                </span>
                <span className="flex items-center gap-1.5 font-mono text-sm tabular-nums text-text">
                  {event.changed ? <GitDiff weight="bold" className="size-3.5 shrink-0 text-conflict" aria-hidden /> : null}
                  {value}
                </span>
                <span className="flex items-center gap-1 text-xs text-text-subtle">
                  {event.selected ? (
                    <>
                      <CheckCircle weight="bold" className="size-3.5 text-accent" aria-hidden />
                      <span className="text-accent">current value</span>
                    </>
                  ) : event.changed ? (
                    <span className="text-conflict">changed</span>
                  ) : index > 0 ? (
                    "no change"
                  ) : (
                    "first source"
                  )}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
      <p className="text-xs text-text-muted">
        {timelineRule(timeline)}
        <span className="text-text-subtle"> Use the arrow keys to step through the sources.</span>
      </p>
    </div>
  );
}
