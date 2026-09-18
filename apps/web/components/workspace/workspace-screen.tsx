"use client";

import { ArrowRight, MagnifyingGlass } from "@phosphor-icons/react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { ErrorNotice } from "@/components/error-notice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, asApiError, type AnswerResult, type ApiError, type QueryResult } from "@/lib/api";

import { AnswerCard } from "./answer-card";
import { DocumentsRail } from "./documents-rail";
import { EvidencePanel, evidenceElementId } from "./evidence-panel";
import { ProviderBanner } from "./provider-banner";
import { useDocuments } from "./use-documents";

/**
 * One question is two calls (ADR-009): retrieve, then answer over exactly what was retrieved. Each
 * phase on screen is one of those calls.
 */
export type AskState =
  | { phase: "idle" }
  | { phase: "retrieving"; question: string }
  | { phase: "answering"; question: string; query: QueryResult }
  | { phase: "done"; question: string; query: QueryResult; answer: AnswerResult }
  | { phase: "error"; question: string; query: QueryResult | null; error: ApiError };

export function WorkspaceScreen() {
  const workspaceId = useSearchParams().get("ws");
  if (!workspaceId) {
    return (
      <main className="mx-auto flex min-h-dvh max-w-[72ch] flex-col justify-center gap-4 px-4">
        <h1 className="text-xl font-semibold text-text">This link has no workspace in it</h1>
        <p className="text-sm text-text-muted">
          Workspace links end in <span className="font-mono">?ws=</span> and the workspace ID. Open
          the link you were given again, or start a new workspace.
        </p>
        <Link href="/" className="text-sm text-accent underline-offset-4 hover:underline">
          Go to the start page
        </Link>
      </main>
    );
  }
  return <Workspace key={workspaceId} workspaceId={workspaceId} />;
}

function Workspace({ workspaceId }: { workspaceId: string }) {
  const docs = useDocuments(workspaceId);
  const [ask, setAsk] = useState<AskState>({ phase: "idle" });
  const [question, setQuestion] = useState("");
  const [highlighted, setHighlighted] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const askInput = useRef<HTMLInputElement>(null);
  const run = useRef(0); // ignores results from a question the user has already replaced

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        askInput.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  async function answerStage(id: number, text: string, query: QueryResult) {
    setAsk({ phase: "answering", question: text, query });
    setAnnouncement("Writing answer");
    try {
      const answer = await api.answer(workspaceId, query.query_id);
      if (run.current !== id) return;
      setAsk({ phase: "done", question: text, query, answer });
      setAnnouncement(
        answer.status === "insufficient_evidence" ? "Not enough evidence" : "Answer ready",
      );
    } catch (error) {
      if (run.current !== id) return;
      const apiError = asApiError(error);
      setAsk({ phase: "error", question: text, query, error: apiError });
      setAnnouncement(apiError.message);
    }
  }

  async function ask_(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    const id = ++run.current;
    setHighlighted(null);
    setAsk({ phase: "retrieving", question: trimmed });
    setAnnouncement("Retrieving evidence");
    let query: QueryResult;
    try {
      query = await api.query(workspaceId, trimmed);
    } catch (error) {
      if (run.current !== id) return;
      const apiError = asApiError(error);
      setAsk({ phase: "error", question: trimmed, query: null, error: apiError });
      setAnnouncement(apiError.message);
      return;
    }
    if (run.current !== id) return;
    setAnnouncement(`${query.evidence.length} passages retrieved`);
    await answerStage(id, trimmed, query);
  }

  function retry() {
    if (ask.phase !== "error") return;
    // A failed answer is retried over the same stored evidence; a failed retrieval asks again.
    if (ask.query) void answerStage(++run.current, ask.question, ask.query);
    else void ask_(ask.question);
  }

  function cite(evidenceId: string) {
    setHighlighted(evidenceId);
    const card = document.getElementById(evidenceElementId(evidenceId));
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // Focus first, so the focus change can't interrupt the scroll.
    card?.focus({ preventScroll: true });
    card?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void ask_(question);
  }

  const workspaceMissing = docs.loadError?.code === "not_found";
  const busy = ask.phase === "retrieving" || ask.phase === "answering";

  return (
    <div className="grid min-h-dvh grid-rows-[auto_1fr] bg-bg lg:h-dvh">
      <header className="flex items-center gap-3 border-b border-border px-4 py-3">
        <Link href="/" className="shrink-0 text-sm font-semibold whitespace-nowrap text-text">
          CROWN-X
        </Link>
        <span className="text-text-subtle" aria-hidden>
          /
        </span>
        <span className="min-w-0 truncate font-mono text-xs text-text-muted" title={workspaceId}>
          {workspaceId}
        </span>
        <div className="ml-auto min-w-0">
          <ProviderBanner />
        </div>
      </header>

      {workspaceMissing && docs.loadError ? (
        <main className="mx-auto flex w-full max-w-[72ch] flex-col gap-4 px-4 py-12">
          <h1 className="text-xl font-semibold text-text">Workspace not found</h1>
          <ErrorNotice
            error={docs.loadError}
            action={
              <Link href="/" className="text-sm text-accent underline-offset-4 hover:underline">
                Start a new workspace
              </Link>
            }
          />
        </main>
      ) : (
        <div className="grid min-h-0 grid-cols-1 lg:grid-cols-[264px_minmax(0,1fr)_400px] lg:grid-rows-[minmax(0,1fr)]">
          <div className="border-b border-border lg:min-h-0 lg:overflow-y-auto lg:border-r lg:border-b-0">
            <DocumentsRail
              documents={docs.documents}
              loadError={docs.loadError}
              uploads={docs.uploads}
              onUpload={docs.upload}
              onDismissUpload={docs.dismissUpload}
              onRetryLoad={() => void docs.refresh()}
            />
          </div>

          <main className="flex min-w-0 flex-col gap-6 p-4 lg:min-h-0 lg:overflow-y-auto lg:px-6">
            <h1 className="sr-only">Workspace</h1>
            <form onSubmit={onSubmit} className="flex flex-col gap-2" role="search">
              <label htmlFor="ask" className="text-sm font-medium text-text">
                Ask the documents
              </label>
              <div className="flex gap-2">
                <div className="relative min-w-0 flex-1">
                  <MagnifyingGlass
                    className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-text-subtle"
                    aria-hidden
                  />
                  <Input
                    id="ask"
                    ref={askInput}
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    maxLength={500}
                    placeholder="What is the current submission deadline?"
                    autoComplete="off"
                    className="h-11 bg-surface pl-9"
                  />
                </div>
                <Button type="submit" className="h-11 px-4" disabled={busy || !question.trim()}>
                  Ask
                  <ArrowRight data-icon="inline-end" />
                </Button>
              </div>
              <p className="text-xs text-text-subtle">
                <kbd className="font-mono">Ctrl K</kbd> focuses this box. Every sentence in an answer
                cites the passages it comes from.
              </p>
            </form>

            <AnswerCard ask={ask} onRetry={retry} onCite={cite} />
          </main>

          <div className="border-t border-border lg:min-h-0 lg:overflow-y-auto lg:border-t-0 lg:border-l">
            <EvidencePanel ask={ask} highlighted={highlighted} />
          </div>
        </div>
      )}

      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
    </div>
  );
}
