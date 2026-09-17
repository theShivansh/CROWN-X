"use client";

import { ArrowRight, CircleNotch, MagnifyingGlass, Question } from "@phosphor-icons/react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { ErrorNotice } from "@/components/error-notice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, asApiError, type ApiError, type QueryResult } from "@/lib/api";

import { DocumentsRail } from "./documents-rail";
import { EvidencePanel } from "./evidence-panel";
import { useDocuments } from "./use-documents";

export type AskState =
  | { phase: "idle" }
  | { phase: "loading"; question: string }
  | { phase: "done"; question: string; result: QueryResult }
  | { phase: "error"; question: string; error: ApiError };

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
  const [announcement, setAnnouncement] = useState("");
  const askInput = useRef<HTMLInputElement>(null);

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

  async function run(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    setAsk({ phase: "loading", question: trimmed });
    setAnnouncement("Retrieving evidence");
    try {
      const result = await api.query(workspaceId, trimmed);
      setAsk({ phase: "done", question: trimmed, result });
      setAnnouncement(
        result.evidence.length ? `${result.evidence.length} passages retrieved` : "Not enough evidence",
      );
    } catch (error) {
      const apiError = asApiError(error);
      setAsk({ phase: "error", question: trimmed, error: apiError });
      setAnnouncement(apiError.message);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void run(question);
  }

  const workspaceMissing = docs.loadError?.code === "not_found";

  return (
    <div className="grid min-h-dvh grid-rows-[auto_1fr] bg-bg">
      <header className="flex items-center gap-3 border-b border-border px-4 py-3">
        <Link href="/" className="text-sm font-semibold text-text">
          CROWN-X
        </Link>
        <span className="text-text-subtle" aria-hidden>
          /
        </span>
        <span className="min-w-0 truncate font-mono text-xs text-text-muted" title={workspaceId}>
          {workspaceId}
        </span>
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
        <div className="grid min-h-0 grid-cols-1 lg:grid-cols-[264px_minmax(0,1fr)_400px]">
          <div className="border-b border-border lg:border-r lg:border-b-0">
            <DocumentsRail
              documents={docs.documents}
              loadError={docs.loadError}
              uploads={docs.uploads}
              onUpload={docs.upload}
              onDismissUpload={docs.dismissUpload}
              onRetryLoad={() => void docs.refresh()}
            />
          </div>

          <main className="flex min-w-0 flex-col gap-6 p-4 lg:px-6">
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
                    placeholder="What is the submission deadline?"
                    autoComplete="off"
                    className="h-11 bg-surface pl-9"
                  />
                </div>
                <Button type="submit" className="h-11 px-4" disabled={ask.phase === "loading" || !question.trim()}>
                  Ask
                  <ArrowRight data-icon="inline-end" />
                </Button>
              </div>
              <p className="text-xs text-text-subtle">
                <kbd className="font-mono">Ctrl K</kbd> focuses this box. Results are the matching
                passages; written answers arrive in the next build.
              </p>
            </form>

            <QuestionStatus ask={ask} onRetry={() => void run(ask.phase === "idle" ? question : ask.question)} />
          </main>

          <div className="border-t border-border lg:border-t-0 lg:border-l">
            <EvidencePanel ask={ask} />
          </div>
        </div>
      )}

      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
    </div>
  );
}

function QuestionStatus({ ask, onRetry }: { ask: AskState; onRetry: () => void }) {
  if (ask.phase === "idle") return null;
  return (
    <section aria-label="Question" className="flex flex-col gap-3 rounded-md border border-border bg-surface p-4">
      <p className="text-base text-text">{ask.question}</p>
      {ask.phase === "loading" ? (
        <p className="flex items-center gap-2 text-sm text-text-muted">
          <CircleNotch className="size-4 animate-spin motion-reduce:animate-none" aria-hidden />
          Retrieving evidence
        </p>
      ) : null}
      {ask.phase === "error" ? (
        <ErrorNotice
          error={ask.error}
          action={
            <Button size="sm" variant="outline" onClick={onRetry}>
              Retry
            </Button>
          }
        />
      ) : null}
      {ask.phase === "done" && ask.result.evidence.length === 0 ? (
        <div className="flex gap-2 text-sm">
          <Question weight="bold" className="mt-0.5 size-4 shrink-0 text-insufficient" aria-hidden />
          <div className="flex flex-col gap-1">
            <p className="font-medium text-text">Not enough evidence</p>
            <p className="text-text-muted">
              No passage in this workspace matches that question. Upload a document that covers it,
              or ask about something else.
            </p>
          </div>
        </div>
      ) : null}
      {ask.phase === "done" && ask.result.evidence.length > 0 ? (
        <p className="text-sm text-text-muted">
          <span className="font-mono tabular-nums text-text">{ask.result.evidence.length}</span>{" "}
          matching passages from{" "}
          <span className="font-mono tabular-nums text-text">
            {new Set(ask.result.evidence.map((e) => e.document_id)).size}
          </span>{" "}
          {new Set(ask.result.evidence.map((e) => e.document_id)).size === 1 ? "document" : "documents"},
          ranked in the evidence panel.
        </p>
      ) : null}
    </section>
  );
}
