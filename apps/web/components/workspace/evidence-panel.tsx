"use client";

import { ChartLineUp, GitDiff, Question } from "@phosphor-icons/react";
import { motion, useReducedMotion } from "motion/react";
import { Fragment } from "react";

import { BorderBeam } from "@/components/ui/border-beam";
import { Skeleton } from "@/components/ui/skeleton";
import type { ConflictGroup, Evidence } from "@/lib/api";
import { displayValue, selectedClaim } from "@/lib/conflicts";
import { cn } from "@/lib/utils";

import type { AskState } from "./workspace-screen";

export function evidenceElementId(evidenceId: string) {
  return `evidence-${evidenceId}`;
}

/**
 * Where each conflict card sits in the ranked list: straight after the first of its sources to
 * appear, so it lands between the two passages that disagree (DESIGN §6).
 */
export function conflictSlots(evidence: Evidence[], conflicts: ConflictGroup[]): Map<string, ConflictGroup[]> {
  const slots = new Map<string, ConflictGroup[]>();
  for (const group of conflicts) {
    const chunks = new Set(group.claims.map((c) => c.source_chunk_id));
    const first = evidence.find((e) => chunks.has(e.chunk_id));
    if (!first) continue;
    slots.set(first.evidence_id, [...(slots.get(first.evidence_id) ?? []), group]);
  }
  return slots;
}

export function EvidencePanel(props: {
  ask: AskState;
  highlighted: string | null;
  onInspect: (key: string) => void;
  onTimeline: (group: ConflictGroup) => void;
}) {
  const { ask, highlighted, onInspect, onTimeline } = props;
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
      <EvidenceBody
        ask={ask}
        evidence={evidence}
        highlighted={highlighted}
        cited={cited}
        onInspect={onInspect}
        onTimeline={onTimeline}
      />
    </aside>
  );
}

function EvidenceBody(props: {
  ask: AskState;
  evidence: Evidence[] | null;
  highlighted: string | null;
  cited: Set<string>;
  onInspect: (key: string) => void;
  onTimeline: (group: ConflictGroup) => void;
}) {
  const { ask, evidence, highlighted, cited, onInspect, onTimeline } = props;
  const reduce = useReducedMotion();
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
  const conflicts = "query" in ask && ask.query ? ask.query.conflicts : [];
  const slots = conflictSlots(evidence, conflicts);
  const comparing = ask.phase === "answering";
  // The signature sequence (DESIGN §6): cards enter in rank order as retrieval returns, 60ms apart;
  // each conflict card follows the first of its sources. Keyed by query, so it plays once per answer.
  let order = 0;
  const enter = () => {
    const delay = order++ * 0.06;
    return reduce
      ? {}
      : {
          initial: { opacity: 0, y: 6 },
          animate: { opacity: 1, y: 0 },
          transition: { duration: 0.28, delay, ease: [0.16, 1, 0.3, 1] as const },
        };
  };
  return (
    <ol key={"query" in ask && ask.query ? ask.query.query_id : "none"} className="flex flex-col gap-2">
      {evidence.map((e) => (
        <Fragment key={e.chunk_id}>
          <motion.li {...enter()} className="list-none">
            <EvidenceCard evidence={e} highlighted={highlighted === e.evidence_id} cited={cited.has(e.evidence_id)} />
          </motion.li>
          {(slots.get(e.evidence_id) ?? []).map((group) => (
            <motion.li key={group.key} {...enter()} className="list-none">
              <ConflictCard group={group} comparing={comparing} onInspect={onInspect} onTimeline={onTimeline} />
            </motion.li>
          ))}
        </Fragment>
      ))}
    </ol>
  );
}

/** The conflict as it sits among the evidence: both values, the current one, and where to look next. */
function ConflictCard(props: {
  group: ConflictGroup;
  comparing: boolean;
  onInspect: (key: string) => void;
  onTimeline: (group: ConflictGroup) => void;
}) {
  const { group, comparing, onInspect, onTimeline } = props;
  const selected = selectedClaim(group);
  const values = [...new Map(group.claims.map((c) => [displayValue(c), c])).keys()];
  return (
    <div className="relative flex flex-col gap-2 rounded-md border border-conflict bg-conflict-soft p-3">
      <BorderBeam active={comparing} />
      <p className="flex items-center gap-2 text-dense font-medium text-text">
        <GitDiff weight="bold" className="size-4 shrink-0 text-conflict" aria-hidden />
        Sources disagree on the {group.label}
      </p>
      <p className="font-mono text-xs tabular-nums text-text">{values.join(" vs ")}</p>
      <p className="text-xs text-text-muted">
        {comparing
          ? `Comparing ${new Set(group.claims.map((c) => c.document_id)).size} sources`
          : selected
            ? `Current value: ${displayValue(selected)}`
            : "No current value chosen"}
      </p>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        <button
          type="button"
          onClick={() => onInspect(group.key)}
          className="inline-flex items-center gap-1 rounded-sm text-xs text-accent underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <GitDiff className="size-3.5" aria-hidden />
          Inspect
        </button>
        <button
          type="button"
          onClick={() => onTimeline(group)}
          className="inline-flex items-center gap-1 rounded-sm text-xs text-accent underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <ChartLineUp className="size-3.5" aria-hidden />
          Timeline
        </button>
      </div>
    </div>
  );
}

function EvidenceCard({ evidence: e, highlighted, cited }: { evidence: Evidence; highlighted: boolean; cited: boolean }) {
  const meta = [e.version_label, e.source_timestamp, e.page_or_section].filter(Boolean).join(" · ");
  return (
    <div
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
    </div>
  );
}
