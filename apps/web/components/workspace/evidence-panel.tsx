"use client";

import { Question } from "@phosphor-icons/react";

import { Skeleton } from "@/components/ui/skeleton";
import type { Evidence } from "@/lib/api";
import { cn } from "@/lib/utils";

import type { AskState } from "./workspace-screen";

export function evidenceElementId(evidenceId: string) {
  return `evidence-${evidenceId}`;
}

export function EvidencePanel({ ask, highlighted }: { ask: AskState; highlighted: string | null }) {
  const evidence = "query" in ask && ask.query ? ask.query.evidence : null;
  const cited = new Set(ask.phase === "done" ? ask.answer.claims.flatMap((c) => c.evidence_ids) : []);
  return (
    <aside aria-labelledby="evidence-heading" className="flex min-h-0 flex-col gap-4 p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h2 id="evidence-heading" className="text-sm font-medium text-text">
          Evidence
        </h2>
        {evidence?.length ? (
          <span className="font-mono text-xs tabular-nums text-text-subtle">{evidence.length} passages</span>
        ) : null}
      </div>
      <EvidenceBody ask={ask} evidence={evidence} highlighted={highlighted} cited={cited} />
    </aside>
  );
}

function EvidenceBody(props: {
  ask: AskState;
  evidence: Evidence[] | null;
  highlighted: string | null;
  cited: Set<string>;
}) {
  const { ask, evidence, highlighted, cited } = props;
  if (ask.phase === "idle") {
    return <p className="text-sm text-text-muted">The passages behind a question appear here.</p>;
  }
  if (ask.phase === "retrieving") {
    return (
      <div className="flex flex-col gap-2" aria-busy>
        <p className="text-xs text-text-muted">Retrieving evidence</p>
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-28 rounded-md bg-surface-2" />
        ))}
      </div>
    );
  }
  if (evidence === null) {
    return <p className="text-sm text-text-muted">No evidence, because the question didn&apos;t reach retrieval.</p>;
  }
  if (evidence.length === 0) {
    return (
      <div className="flex gap-2 text-sm text-text-muted">
        <Question weight="bold" className="mt-0.5 size-4 shrink-0 text-insufficient" aria-hidden />
        <p>No passage in this workspace matches the question.</p>
      </div>
    );
  }
  return (
    <ol className="flex flex-col gap-2">
      {evidence.map((e) => (
        <EvidenceCard key={e.chunk_id} evidence={e} highlighted={highlighted === e.evidence_id} cited={cited.has(e.evidence_id)} />
      ))}
    </ol>
  );
}

function EvidenceCard({ evidence: e, highlighted, cited }: { evidence: Evidence; highlighted: boolean; cited: boolean }) {
  const meta = [e.version_label, e.source_timestamp, e.page_or_section].filter(Boolean).join(" · ");
  return (
    <li
      id={evidenceElementId(e.evidence_id)}
      tabIndex={-1}
      className={cn(
        "flex scroll-mt-4 flex-col gap-2 rounded-md border bg-surface p-3 transition-colors duration-(--duration-base) ease-out focus-visible:outline-none",
        highlighted ? "border-accent bg-accent-soft" : "border-border",
      )}
    >
      <div className="flex items-baseline gap-2">
        <span className={cn("font-mono text-xs tabular-nums", cited ? "text-accent" : "text-text-subtle")}>
          [{e.retrieval_rank}]
        </span>
        <p className="min-w-0 truncate text-dense font-medium text-text" title={e.filename ?? e.document_id}>
          {e.filename ?? e.document_id}
        </p>
      </div>
      {meta ? <p className="font-mono text-xs tabular-nums text-text-muted">{meta}</p> : null}
      <blockquote className="font-mono text-xs whitespace-pre-wrap break-words text-text">
        {highlighted ? <mark className="rounded-sm bg-accent-soft text-text">{e.quoted_span}</mark> : e.quoted_span}
      </blockquote>
      <p className="font-mono text-xs tabular-nums break-all text-text-subtle">
        {e.chunk_id} · chars {e.char_start}-{e.char_end}
      </p>
    </li>
  );
}
