"use client";

import { ArrowRight, ClockClockwise, GitDiff } from "@phosphor-icons/react";

import { BorderBeam } from "@/components/ui/border-beam";
import { Disclosure } from "@/components/ui/disclosure";
import type { Claim, ConflictGroup, Evidence } from "@/lib/api";
import {
  displayValue,
  formatDate,
  normalizedValue,
  primaryPair,
  ruleSentence,
  selectedClaim,
  sourceLine,
  timeline,
  timelineOrder,
  whyFlagged,
} from "@/lib/conflicts";
import { cn } from "@/lib/utils";

export function conflictElementId(key: string) {
  return `conflict-${key.replace(/[^a-z0-9]+/gi, "-")}`;
}

const TYPE_WORD = { date: "Date", number: "Number", owner: "Owner" } as const;

/**
 * UI_UX §3.5, the conflict inspector: older source on the left, newer on the right, the rule that
 * chose the current value, how the value changed across every source, and why code flagged it.
 * Rendered from the conflict data only, never from the answer text.
 */
export function ConflictInspector(props: {
  group: ConflictGroup;
  evidence: Evidence[];
  comparing: boolean;
  onOpen: (evidenceId: string) => void;
}) {
  const { group, evidence, comparing, onOpen } = props;
  const { older, newer } = primaryPair(group);
  const selected = selectedClaim(group);
  const evidenceFor = (claim: Claim) => evidence.find((e) => e.chunk_id === claim.source_chunk_id) ?? null;
  const headingId = `${conflictElementId(group.key)}-heading`;

  return (
    <section
      id={conflictElementId(group.key)}
      tabIndex={-1}
      aria-labelledby={headingId}
      className="relative flex scroll-mt-4 flex-col gap-4 rounded-md border border-border bg-surface p-4 focus-visible:outline-none"
    >
      <BorderBeam active={comparing} />
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h3 id={headingId} className="flex items-center gap-2 text-sm font-medium text-text">
          <GitDiff weight="bold" className="size-4 text-conflict" aria-hidden />
          {TYPE_WORD[group.type]} conflict on {group.label}
        </h3>
        <span className="font-mono text-xs text-text-subtle">
          {group.severity} severity · {group.pairs.length} {group.pairs.length === 1 ? "pair" : "pairs"}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <Side claim={older} letter="A" newer={null} evidence={evidenceFor(older)} onOpen={onOpen} />
        <Side
          claim={newer}
          letter="B"
          newer={selected && normalizedValue(selected) === normalizedValue(newer) ? group : null}
          evidence={evidenceFor(newer)}
          onOpen={onOpen}
        />
      </div>

      <p className="text-sm text-text">{ruleSentence(group)}</p>

      <Timeline group={group} evidence={evidence} onOpen={onOpen} />

      <Disclosure label="Why was this flagged?">
        <ul className="flex flex-col gap-1 text-xs leading-5 text-text-muted">
          {whyFlagged(group, older, newer).map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </Disclosure>
    </section>
  );
}

function Side(props: {
  claim: Claim;
  letter: "A" | "B";
  newer: ConflictGroup | null;
  evidence: Evidence | null;
  onOpen: (evidenceId: string) => void;
}) {
  const { claim, letter, newer, evidence, onOpen } = props;
  const source = sourceLine(claim);
  const start = claim.value_start - claim.char_start;
  const end = claim.value_end - claim.char_start;
  return (
    <div
      className={cn(
        "flex min-w-0 flex-col gap-2 rounded-sm border bg-surface-2 p-3",
        newer ? "border-accent" : "border-border",
      )}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-1">
        <p className="min-w-0 truncate font-mono text-xs text-text-muted" title={source.name}>
          {source.name}
          {source.version ? ` · ${source.version}` : ""} · {source.date}
        </p>
        {newer ? (
          <span className="inline-flex items-center gap-1 text-xs text-accent">
            <ClockClockwise className="size-3.5" aria-hidden />
            {/* Name what decided it: a date only when the rule was the source date. */}
            {newer.selection_rule === "newest_source_timestamp" && claim.source_timestamp
              ? `Newer · ${formatDate(claim.source_timestamp, false)}`
              : newer.selection_rule === "version_order"
                ? `Newer version${claim.version_label ? ` · ${claim.version_label}` : ""}`
                : "Uploaded later"}
          </span>
        ) : null}
      </div>
      <blockquote className="font-mono text-xs leading-5 break-words text-text">
        “{claim.quote.slice(0, start)}
        <mark className="rounded-sm bg-conflict-soft px-0.5 text-text">{claim.quote.slice(start, end)}</mark>
        {claim.quote.slice(end)}”
      </blockquote>
      <p className="font-mono text-xs tabular-nums text-text-muted">
        value: <span className="text-text">{normalizedValue(claim)}</span>
      </p>
      {evidence ? (
        <button
          type="button"
          onClick={() => onOpen(evidence.evidence_id)}
          className="inline-flex w-fit items-center gap-1 rounded-sm text-xs text-accent underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          Open source {letter}
          <span className="font-mono tabular-nums">[{evidence.retrieval_rank}]</span>
        </button>
      ) : (
        <p className="text-xs text-text-subtle">
          Source {letter} wasn&apos;t among the retrieved passages; the quote above is exact.
        </p>
      )}
    </div>
  );
}

function Timeline(props: { group: ConflictGroup; evidence: Evidence[]; onOpen: (evidenceId: string) => void }) {
  const { group, evidence, onOpen } = props;
  const points = timeline(group);
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-text-muted">
        How the value changed. <span className="text-text-subtle">{timelineOrder(group)}</span>
      </p>
      <ol aria-label={`How the ${group.label} changed`} className="flex flex-wrap items-stretch gap-2">
        {points.map((point, index) => {
          const passage = evidence.find((e) => e.chunk_id === point.claim.source_chunk_id);
          return (
            <li key={point.claim.claim_id} className="flex items-center gap-2">
              {index > 0 ? <ArrowRight className="size-3.5 shrink-0 text-text-subtle" aria-hidden /> : null}
              <button
                type="button"
                // Focusable either way: a point whose passage wasn't retrieved still reads out.
                aria-disabled={!passage}
                onClick={() => passage && onOpen(passage.evidence_id)}
                aria-label={`${point.label}, ${point.claim.filename}: ${displayValue(point.claim)}${
                  point.changed ? ", value changed" : index > 0 ? ", no change" : ""
                }${point.selected ? ", current value" : ""}`}
                className={cn(
                  "flex min-w-32 flex-col items-start gap-0.5 rounded-sm border px-2.5 py-2 text-left transition-colors duration-(--duration-fast) ease-out focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none hover:bg-surface-3 aria-disabled:cursor-default aria-disabled:hover:bg-surface-2",
                  point.selected ? "border-accent bg-accent-soft" : "border-border bg-surface-2",
                )}
              >
                <span className="font-mono text-xs tabular-nums text-text-muted">{point.label}</span>
                <span className="max-w-44 truncate text-xs text-text-subtle">{point.claim.filename}</span>
                <span className="flex items-center gap-1 font-mono text-xs tabular-nums text-text">
                  {point.changed ? <GitDiff weight="bold" className="size-3.5 text-conflict" aria-hidden /> : null}
                  {displayValue(point.claim)}
                </span>
                <span className="text-xs text-text-subtle">
                  {point.selected ? "current value" : point.changed ? "changed" : index > 0 ? "no change" : "first"}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
