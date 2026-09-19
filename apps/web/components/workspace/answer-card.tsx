"use client";

import { Check, CircleNotch, Copy, GitDiff, Question, SealCheck, SealWarning } from "@phosphor-icons/react";
import { useState } from "react";

import { ErrorNotice } from "@/components/error-notice";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { fellBack, type AnswerResult, type ConflictGroup, type Evidence } from "@/lib/api";
import { conflictSummary, ruleSentence } from "@/lib/conflicts";

import type { AskState } from "./workspace-screen";

/** UI_UX §3.3: the answer card in each of its states, with citation chips that open the evidence. */
export function AnswerCard(props: {
  ask: AskState;
  onRetry: () => void;
  onCite: (evidenceId: string) => void;
  onInspect: (key: string) => void;
  onCopied?: (queryId: string) => void;
}) {
  const { ask, onRetry, onCite, onInspect, onCopied } = props;
  if (ask.phase === "idle") return null;

  return (
    <section aria-label="Answer" className="flex flex-col gap-3 rounded-md border border-border bg-surface p-4">
      <p className="text-base text-text">{ask.question}</p>
      {ask.phase === "retrieving" || ask.phase === "answering" ? (
        <div className="flex flex-col gap-2" aria-busy>
          <p className="flex items-center gap-2 text-sm text-text-muted">
            <CircleNotch className="size-4 animate-spin motion-reduce:animate-none" aria-hidden />
            {ask.phase === "retrieving" ? "Retrieving evidence" : writingStage(ask.query.evidence, ask.query.conflicts)}
          </p>
          <Skeleton className="h-4 w-11/12 rounded-sm bg-surface-2" />
          <Skeleton className="h-4 w-8/12 rounded-sm bg-surface-2" />
        </div>
      ) : null}
      {ask.phase === "error" ? (
        <ErrorNotice
          error={ask.error}
          action={
            <Button size="sm" variant="outline" onClick={onRetry}>
              {ask.query ? "Retry the answer" : "Retry"}
            </Button>
          }
        />
      ) : null}
      {ask.phase === "done" ? (
        <Answered
          answer={ask.answer}
          evidence={ask.query.evidence}
          conflicts={ask.query.conflicts}
          onCite={onCite}
          onInspect={onInspect}
          onCopied={onCopied ? () => onCopied(ask.query.query_id) : undefined}
        />
      ) : null}
    </section>
  );
}

/** UI_UX §3.3 loading text: name the work. Comparing happens only when code found conflicts. */
function writingStage(evidence: Evidence[], conflicts: ConflictGroup[]): string {
  const passages = `${evidence.length} ${evidence.length === 1 ? "passage" : "passages"}`;
  if (!conflicts.length) return `Writing answer from ${passages}`;
  const sources = new Set(conflicts.flatMap((g) => g.claims.map((c) => c.document_id))).size;
  return `Comparing ${sources} sources, writing answer from ${passages}`;
}

function Answered({
  answer,
  evidence,
  conflicts,
  onCite,
  onInspect,
  onCopied,
}: {
  answer: AnswerResult;
  evidence: Evidence[];
  conflicts: ConflictGroup[];
  onCite: (evidenceId: string) => void;
  onInspect: (key: string) => void;
  onCopied?: () => void;
}) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    // The answer with its citations and the sources they point to, as plain text.
    const byId = new Map(evidence.map((e) => [e.evidence_id, e]));
    const lines = answer.claims.map(
      (c) => `${c.text} ${c.evidence_ids.map((id) => `[${byId.get(id)?.retrieval_rank ?? "?"}]`).join("")}`,
    );
    const cited = [...new Set(answer.claims.flatMap((c) => c.evidence_ids))]
      .map((id) => byId.get(id))
      .filter((e): e is Evidence => Boolean(e))
      .sort((a, b) => a.retrieval_rank - b.retrieval_rank)
      .map((e) => `[${e.retrieval_rank}] ${e.filename ?? e.document_id}${e.page_or_section ? `, ${e.page_or_section}` : ""}`);
    try {
      await navigator.clipboard.writeText([...lines, "", "Sources:", ...cited].join("\n"));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
      onCopied?.();
    } catch {
      setCopied(false);
    }
  }
  const rankOf = new Map(evidence.map((e) => [e.evidence_id, e.retrieval_rank]));
  const sources = new Set(
    answer.claims.flatMap((c) => c.evidence_ids.map((id) => evidence.find((e) => e.evidence_id === id)?.document_id)),
  );
  sources.delete(undefined);

  if (answer.status === "insufficient_evidence") {
    return (
      <div className="flex gap-2 text-sm">
        <Question weight="bold" className="mt-0.5 size-4 shrink-0 text-insufficient" aria-hidden />
        <div className="flex flex-col gap-1">
          <p className="font-medium text-text">Not enough evidence</p>
          <p className="text-text-muted">{answer.answer}</p>
          {evidence.length ? (
            <p className="text-text-subtle">
              {evidence.length} {evidence.length === 1 ? "passage was" : "passages were"} searched; none
              states the answer.
            </p>
          ) : null}
        </div>
      </div>
    );
  }

  const partial = answer.status === "partial";
  return (
    <div className="flex flex-col gap-3">
      {answer.status === "conflict" && conflicts.length ? (
        <div className="flex flex-col gap-2 rounded-sm border border-border bg-surface-2 p-3">
          <p className="flex items-center gap-1.5 text-xs font-medium text-text">
            <GitDiff weight="bold" className="size-4 text-conflict" aria-hidden />
            Sources disagree
          </p>
          {/* From the conflict data, never from the answer text (ADR-003). */}
          {conflicts.map((group) => (
            <div key={group.key} className="flex flex-col gap-1 text-sm">
              <p className="text-text">
                <span className="text-text-muted">{group.label}: </span>
                {conflictSummary(group)}.
              </p>
              <p className="text-text-muted">{ruleSentence(group)}</p>
              <button
                type="button"
                onClick={() => onInspect(group.key)}
                className="w-fit rounded-sm text-xs text-accent underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                Open the inspector
              </button>
            </div>
          ))}
        </div>
      ) : null}
      <p className="flex items-center gap-1.5 text-xs">
        {answer.status === "conflict" ? (
          <>
            <SealCheck weight="bold" className="size-4 text-text-muted" aria-hidden />
            <span className="text-text">
              Every sentence cites {sources.size} {sources.size === 1 ? "source" : "sources"}
            </span>
          </>
        ) : partial ? (
          <>
            <SealWarning weight="bold" className="size-4 text-text-muted" aria-hidden />
            <span className="text-text">Partly supported: sentences without evidence were removed</span>
          </>
        ) : (
          <>
            <SealCheck weight="bold" className="size-4 text-grounded" aria-hidden />
            <span className="text-text">
              Supported by {sources.size} {sources.size === 1 ? "source" : "sources"}
            </span>
          </>
        )}
      </p>
      <ol className="flex flex-col gap-2">
        {answer.claims.map((claim, index) => (
          <li key={index} className="text-sm leading-6 text-text">
            {claim.text}{" "}
            {claim.evidence_ids.map((id) => (
              <button
                key={id}
                type="button"
                onClick={() => onCite(id)}
                className="mx-0.5 inline-flex h-5 min-w-6 items-center justify-center rounded-sm bg-accent-soft px-1 font-mono text-xs tabular-nums text-accent transition-colors duration-(--duration-fast) ease-out hover:bg-accent hover:text-accent-fg focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                aria-label={`Open evidence ${rankOf.get(id) ?? id}`}
              >
                [{rankOf.get(id) ?? "?"}]
              </button>
            ))}
          </li>
        ))}
      </ol>
      {answer.claims.length ? (
        <button
          type="button"
          onClick={() => void copy()}
          className="inline-flex w-fit items-center gap-1 rounded-sm text-xs text-accent underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          {copied ? <Check className="size-3.5" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
          <span aria-live="polite">{copied ? "Copied with sources" : "Copy answer"}</span>
        </button>
      ) : null}
      {answer.answer_provider ? (
        <p className="font-mono text-xs text-text-subtle">
          {answer.answer_provider} · {answer.answered_by_model ?? answer.model_id}
          {fellBack(answer) ? <span className="text-text-muted"> · fallback model, primary was busy</span> : null}
        </p>
      ) : null}
    </div>
  );
}
