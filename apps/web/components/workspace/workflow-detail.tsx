"use client";

import { X } from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { WorkflowSuggestion, WorkflowTemplate } from "@/lib/api";
import { confidenceSentence, stepLabel, supportSentence } from "@/lib/workflows";

const time = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

/**
 * UI_UX §3.7 detail: the ordered steps on the left, the event traces that matched on the right
 * (each step's time and event ID), and the saved versions at the bottom, with a rename on save.
 */
export function WorkflowDetail(props: {
  open: boolean;
  suggestion: WorkflowSuggestion;
  templates: WorkflowTemplate[];
  busy: boolean;
  onSave: (name: string) => void;
  onClose: () => void;
}) {
  const { open, suggestion, templates, busy, onSave, onClose } = props;
  const dialog = useRef<HTMLDialogElement>(null);
  const [name, setName] = useState(suggestion.name.slice(0, 40));

  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  const versions = templates
    .filter((t) => t.suggestion_id === suggestion.suggestion_id)
    .sort((a, b) => b.version - a.version);

  return (
    <dialog
      ref={dialog}
      aria-labelledby="workflow-detail-heading"
      onClose={onClose}
      className="mx-auto mt-[8vh] max-h-[84vh] w-[min(880px,calc(100vw-2rem))] overflow-y-auto rounded-lg border border-border-strong bg-surface-2 p-0 text-text backdrop:bg-bg/70"
    >
      <div className="flex items-start justify-between gap-3 border-b border-border p-4">
        <div className="flex min-w-0 flex-col gap-1">
          <h2 id="workflow-detail-heading" className="text-base font-medium text-text">
            {suggestion.name}
          </h2>
          <p className="text-xs text-text-muted">
            {supportSentence(suggestion)} {confidenceSentence(suggestion)} Nothing runs automatically.
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="inline-flex size-7 shrink-0 items-center justify-center rounded-sm text-text-muted hover:bg-surface-3 hover:text-text focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <X className="size-4" aria-hidden />
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 p-4 md:grid-cols-[220px_minmax(0,1fr)]">
        <section aria-labelledby="wf-steps" className="flex flex-col gap-2">
          <h3 id="wf-steps" className="text-xs font-medium text-text-muted">
            Steps, in order
          </h3>
          <ol className="flex flex-col gap-1.5">
            {suggestion.steps.map((step, i) => (
              <li key={`${step}-${i}`} className="flex gap-2 text-sm text-text">
                <span className="w-4 shrink-0 text-right font-mono text-xs tabular-nums text-text-subtle">{i + 1}</span>
                {stepLabel(step)}
              </li>
            ))}
          </ol>
        </section>

        <section aria-labelledby="wf-traces" className="flex min-w-0 flex-col gap-2">
          <h3 id="wf-traces" className="text-xs font-medium text-text-muted">
            The events that matched ({suggestion.traces.length} most recent)
          </h3>
          <ol className="flex flex-col gap-2">
            {suggestion.traces.map((trace, t) => (
              <li key={trace.join("")} className="rounded-sm border border-border bg-surface p-2">
                <p className="mb-1 font-mono text-xs text-text-subtle">
                  occurrence {t + 1} · session {suggestion.trace_sessions[t]?.slice(4, 10)}
                </p>
                <ol className="flex flex-col gap-0.5">
                  {suggestion.steps.map((step, i) => (
                    <li key={i} className="grid grid-cols-[64px_minmax(0,1fr)] gap-2 font-mono text-xs tabular-nums">
                      <span className="text-text-muted">{time(suggestion.trace_times[t]?.[i] ?? "")}</span>
                      <span className="min-w-0 truncate text-text" title={trace.join(", ")}>
                        {stepLabel(step)}
                      </span>
                    </li>
                  ))}
                </ol>
              </li>
            ))}
          </ol>
        </section>
      </div>

      <section aria-labelledby="wf-save" className="flex flex-col gap-2 border-t border-border p-4">
        <h3 id="wf-save" className="text-xs font-medium text-text-muted">
          Saved versions
        </h3>
        {versions.length ? (
          <ul className="flex flex-col gap-1">
            {versions.map((v) => (
              <li key={v.version} className="font-mono text-xs tabular-nums text-text">
                v{v.version} · {v.name} · {new Date(v.saved_at).toLocaleString("en-GB")}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-text-muted">Not saved yet.</p>
        )}
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            onSave(name.trim());
          }}
        >
          <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs text-text-muted">
            Name
            <Input value={name} onChange={(e) => setName(e.target.value)} minLength={3} maxLength={40} required />
          </label>
          <Button type="submit" disabled={busy || name.trim().length < 3}>
            {versions.length ? `Save as v${versions[0].version + 1}` : "Save workflow"}
          </Button>
        </form>
      </section>
    </dialog>
  );
}
