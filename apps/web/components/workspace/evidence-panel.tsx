"use client";

import { Question } from "@phosphor-icons/react";

import { Skeleton } from "@/components/ui/skeleton";
import type { Evidence } from "@/lib/api";

import type { AskState } from "./workspace-screen";

export function EvidencePanel({ ask }: { ask: AskState }) {
  return (
    <aside aria-labelledby="evidence-heading" className="flex min-h-0 flex-col gap-4 p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h2 id="evidence-heading" className="text-sm font-medium text-text">
          Evidence
        </h2>
        {ask.phase === "done" && ask.result.evidence.length ? (
          <span className="font-mono text-xs tabular-nums text-text-subtle">
            {ask.result.evidence.length} passages
          </span>
        ) : null}
      </div>
      <EvidenceBody ask={ask} />
    </aside>
  );
}

function EvidenceBody({ ask }: { ask: AskState }) {
  if (ask.phase === "idle") {
    return <p className="text-sm text-text-muted">The passages behind a question appear here.</p>;
  }
  if (ask.phase === "loading") {
    return (
      <div className="flex flex-col gap-2" aria-busy>
        <p className="text-xs text-text-muted">Retrieving evidence</p>
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-28 rounded-md bg-surface-2" />
        ))}
      </div>
    );
  }
  if (ask.phase === "error") {
    return <p className="text-sm text-text-muted">No evidence, because the question didn&apos;t reach retrieval.</p>;
  }
  if (ask.result.evidence.length === 0) {
    return (
      <div className="flex gap-2 text-sm text-text-muted">
        <Question weight="bold" className="mt-0.5 size-4 shrink-0 text-insufficient" aria-hidden />
        <p>No passage in this workspace matches the question.</p>
      </div>
    );
  }
  return (
    <ol className="flex min-h-0 flex-col gap-2 overflow-y-auto">
      {ask.result.evidence.map((e) => (
        <EvidenceCard key={e.chunk_id} evidence={e} />
      ))}
    </ol>
  );
}

function EvidenceCard({ evidence: e }: { evidence: Evidence }) {
  return (
    <li className="flex flex-col gap-2 rounded-md border border-border bg-surface p-3">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-xs tabular-nums text-accent">[{e.retrieval_rank}]</span>
        <p className="min-w-0 truncate text-dense font-medium text-text" title={e.filename ?? e.document_id}>
          {e.filename ?? e.document_id}
        </p>
      </div>
      {e.page_or_section ? <p className="text-xs text-text-muted">{e.page_or_section}</p> : null}
      <blockquote className="font-mono text-xs whitespace-pre-wrap break-words text-text">{e.quoted_span}</blockquote>
      <p className="font-mono text-xs tabular-nums break-all text-text-subtle">
        {e.chunk_id} · chars {e.char_start}-{e.char_end}
      </p>
    </li>
  );
}
