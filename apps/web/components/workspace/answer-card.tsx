"use client";

import { CircleNotch, Question, SealCheck, SealWarning } from "@phosphor-icons/react";

import { ErrorNotice } from "@/components/error-notice";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { AnswerResult, Evidence } from "@/lib/api";

import type { AskState } from "./workspace-screen";

/** UI_UX §3.3: the answer card in each of its states, with citation chips that open the evidence. */
export function AnswerCard(props: {
  ask: AskState;
  onRetry: () => void;
  onCite: (evidenceId: string) => void;
}) {
  const { ask, onRetry, onCite } = props;
  if (ask.phase === "idle") return null;

  return (
    <section aria-label="Answer" className="flex flex-col gap-3 rounded-md border border-border bg-surface p-4">
      <p className="text-base text-text">{ask.question}</p>
      {ask.phase === "retrieving" || ask.phase === "answering" ? (
        <div className="flex flex-col gap-2" aria-busy>
          <p className="flex items-center gap-2 text-sm text-text-muted">
            <CircleNotch className="size-4 animate-spin motion-reduce:animate-none" aria-hidden />
            {ask.phase === "retrieving"
              ? "Retrieving evidence"
              : `Writing answer from ${ask.query.evidence.length} ${ask.query.evidence.length === 1 ? "passage" : "passages"}`}
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
      {ask.phase === "done" ? <Answered answer={ask.answer} evidence={ask.query.evidence} onCite={onCite} /> : null}
    </section>
  );
}

function Answered({
  answer,
  evidence,
  onCite,
}: {
  answer: AnswerResult;
  evidence: Evidence[];
  onCite: (evidenceId: string) => void;
}) {
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
      <p className="flex items-center gap-1.5 text-xs">
        {partial ? (
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
      {answer.answer_provider ? (
        <p className="font-mono text-xs text-text-subtle">
          {answer.answer_provider} · {answer.model_id}
        </p>
      ) : null}
    </div>
  );
}
