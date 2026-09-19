"use client";

import { ArrowRight, GitDiff, MagnifyingGlass, Quotes, X } from "@phosphor-icons/react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import { ErrorNotice } from "@/components/error-notice";
import { AnimatedNumber } from "@/components/ui/animated-number";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { WORKFLOWS_ENABLED, track } from "@/lib/events";
import { cn } from "@/lib/utils";
import {
  api,
  asApiError,
  type AnswerResult,
  type ApiError,
  type ConflictGroup,
  type QueryResult,
} from "@/lib/api";

import { AnswerCard } from "./answer-card";
import { AskPalette } from "./ask-palette";
import { ConflictInspector, conflictElementId } from "./conflict-inspector";
import { DocumentsRail } from "./documents-rail";
import { EvidencePanel, evidenceElementId } from "./evidence-panel";
import { ProviderBanner } from "./provider-banner";
import { useDocuments } from "./use-documents";
import { TIMELINE_ELEMENT_ID, ValueTimeline } from "./value-timeline";
import { WorkflowCard } from "./workflow-card";

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

const RECENT_LIMIT = 8;

/** Recent questions live in this browser only, per workspace: a convenience, never state. */
function readRecent(workspaceId: string): string[] {
  try {
    const stored = JSON.parse(window.localStorage.getItem(`crownx.recent.${workspaceId}`) ?? "[]");
    return Array.isArray(stored) ? stored.filter((q) => typeof q === "string").slice(0, RECENT_LIMIT) : [];
  } catch {
    return [];
  }
}

function saveRecent(workspaceId: string, questions: string[]) {
  try {
    window.localStorage.setItem(`crownx.recent.${workspaceId}`, JSON.stringify(questions));
  } catch {
    // Private windows and blocked storage: the palette just shows no recent questions.
  }
}

function Workspace({ workspaceId }: { workspaceId: string }) {
  const docs = useDocuments(workspaceId);
  const [ask, setAsk] = useState<AskState>({ phase: "idle" });
  const [question, setQuestion] = useState("");
  const [highlighted, setHighlighted] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [conflicts, setConflicts] = useState<ConflictGroup[] | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [workflowRefresh, setWorkflowRefresh] = useState(0); // bumped when an answer settles // the evidence sheet, 1024-1279px only
  const [recent, setRecent] = useState<string[]>([]);
  const readyCount = (docs.documents ?? []).filter((d) => d.status === "ready").length;
  const [timelineFor, setTimelineFor] = useState<{ key: string; label: string } | null>(null);
  const askInput = useRef<HTMLInputElement>(null);
  const run = useRef(0); // ignores results from a question the user has already replaced

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setSheetOpen(false);
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setRecent(readRecent(workspaceId));
        setPaletteOpen(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [workspaceId]);

  // The workspace's conflicts, for the header counter and the rail; refetched when a document lands.
  useEffect(() => {
    let live = true;
    api
      .conflicts(workspaceId)
      .then((body) => live && setConflicts(body.conflicts))
      .catch(() => live && setConflicts(null)); // the counter hides; the workspace still works
    return () => {
      live = false;
    };
  }, [workspaceId, readyCount]);

  const conflictsByDocument = useMemo(() => {
    const counts = new Map<string, number>();
    for (const group of conflicts ?? []) {
      const documentOf = new Map(group.claims.map((c) => [c.claim_id, c.document_id]));
      for (const pair of group.pairs) {
        for (const claim of [pair.claim_a, pair.claim_b]) {
          const doc = documentOf.get(claim);
          if (doc) counts.set(doc, (counts.get(doc) ?? 0) + 1);
        }
      }
    }
    return counts;
  }, [conflicts]);
  const conflictCount = (conflicts ?? []).reduce((n, g) => n + g.pairs.length, 0);

  async function answerStage(id: number, text: string, query: QueryResult) {
    setAsk({ phase: "answering", question: text, query });
    setAnnouncement("Writing answer");
    try {
      const answer = await api.answer(workspaceId, query.query_id);
      if (run.current !== id) return;
      setAsk({ phase: "done", question: text, query, answer });
      setWorkflowRefresh((n) => n + 1);
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
    const kept = [trimmed, ...readRecent(workspaceId).filter((q) => q !== trimmed)].slice(0, RECENT_LIMIT);
    saveRecent(workspaceId, kept);
    setQuestion(trimmed);
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

  function cite(evidenceId: string, attempt = 0) {
    if (attempt === 0) track(workspaceId, "evidence_opened", { evidence_id: evidenceId });
    setHighlighted(evidenceId);
    setSheetOpen(true); // a no-op where the evidence is a pane
    const card = document.getElementById(evidenceElementId(evidenceId));
    if (card && !card.checkVisibility({ visibilityProperty: true }) && attempt < 20) {
      // The sheet opens on the next render; a hidden element can't take focus, so try again shortly.
      window.setTimeout(() => cite(evidenceId, attempt + 1), 16);
      return;
    }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // Focus first, so the focus change can't interrupt the scroll.
    card?.focus({ preventScroll: true });
    card?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }

  function inspect(key: string) {
    track(workspaceId, "conflict_opened", { key });
    const card = document.getElementById(conflictElementId(key));
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    card?.focus({ preventScroll: true });
    card?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }

  function openTimeline(group: Pick<ConflictGroup, "key" | "label">) {
    track(workspaceId, "timeline_opened", { key: group.key });
    setTimelineFor({ key: group.key, label: group.label });
    setAnnouncement(`Timeline for the ${group.label}`);
    // After it renders: bring it into view and move focus to it.
    requestAnimationFrame(() => {
      const panel = document.getElementById(TIMELINE_ELEMENT_ID);
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      panel?.focus({ preventScroll: true });
      panel?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    });
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void ask_(question);
  }

  const workspaceMissing = docs.loadError?.code === "not_found";
  const busy = ask.phase === "retrieving" || ask.phase === "answering";
  const shown = "query" in ask && ask.query ? ask.query : null;

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
        {docs.documents ? (
          <dl className="ml-auto hidden shrink-0 items-baseline gap-4 text-xs text-text-muted md:flex">
            <div className="flex items-baseline gap-1.5">
              <dt className="sr-only">Documents indexed</dt>
              <dd>
                <AnimatedNumber value={readyCount} className="font-mono text-sm tabular-nums text-text" />{" "}
                {readyCount === 1 ? "document" : "documents"} indexed
              </dd>
            </div>
            {conflicts ? (
              <div className="flex items-baseline gap-1.5">
                <dt className="sr-only">Conflicts found</dt>
                <dd className="inline-flex items-baseline gap-1">
                  <GitDiff weight="bold" className="size-3.5 self-center text-conflict" aria-hidden />
                  <AnimatedNumber value={conflictCount} className="font-mono text-sm tabular-nums text-text" />{" "}
                  {conflictCount === 1 ? "conflict" : "conflicts"} found
                </dd>
              </div>
            ) : null}
          </dl>
        ) : null}
        <button
          type="button"
          onClick={() => setSheetOpen((open) => !open)}
          aria-expanded={sheetOpen}
          aria-controls="evidence-sheet"
          className="hidden h-8 shrink-0 items-center gap-1.5 rounded-sm border border-border px-2.5 text-xs text-text transition-colors duration-(--duration-fast) ease-out hover:bg-surface-3 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none lg:inline-flex xl:hidden"
        >
          <Quotes className="size-3.5" aria-hidden />
          Evidence
          {shown ? <span className="font-mono tabular-nums text-text-muted">{shown.evidence.length}</span> : null}
        </button>
        <div className={docs.documents ? "min-w-0" : "ml-auto min-w-0"}>
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
        <div className="grid min-h-0 grid-cols-1 lg:grid-cols-[264px_minmax(0,1fr)] lg:grid-rows-[minmax(0,1fr)] xl:grid-cols-[264px_minmax(0,1fr)_400px]">
          <div className="border-b border-border lg:min-h-0 lg:overflow-y-auto lg:border-r lg:border-b-0">
            <DocumentsRail
              documents={docs.documents}
              loadError={docs.loadError}
              uploads={docs.uploads}
              onUpload={docs.upload}
              onDismissUpload={docs.dismissUpload}
              onRetryLoad={() => void docs.refresh()}
              conflictsByDocument={conflictsByDocument}
              footer={
                WORKFLOWS_ENABLED ? <WorkflowCard workspaceId={workspaceId} refreshKey={workflowRefresh} /> : null
              }
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
                <kbd className="font-mono">Ctrl K</kbd> opens Ask CROWN, with your recent questions and the
                workspace&apos;s conflicts. Every sentence in an answer
                cites the passages it comes from.
              </p>
            </form>

            <AnswerCard
              ask={ask}
              onRetry={retry}
              onCite={cite}
              onInspect={inspect}
              onCopied={(queryId) => track(workspaceId, "answer_copied", { query_id: queryId })}
            />

            {shown?.conflicts.length ? (
              <section aria-label="Conflict inspector" className="flex flex-col gap-3">
                <h2 className="text-sm font-medium text-text">
                  Conflicts in this evidence{" "}
                  <span className="font-mono text-xs tabular-nums text-text-subtle">
                    {shown.conflicts.length}
                  </span>
                </h2>
                {shown.conflicts.map((group) => (
                  <ConflictInspector
                    key={group.key}
                    group={group}
                    evidence={shown.evidence}
                    comparing={ask.phase === "answering"}
                    onOpen={cite}
                    onTimeline={openTimeline}
                  />
                ))}
              </section>
            ) : null}

            {timelineFor ? (
              <ValueTimeline
                key={timelineFor.key}
                workspaceId={workspaceId}
                factKey={timelineFor.key}
                label={timelineFor.label}
                evidence={shown?.evidence ?? []}
                onOpen={cite}
                onClose={() => setTimelineFor(null)}
              />
            ) : null}
          </main>

          {/* UI_UX §4: a right sheet from 1024 to 1279px, a pane from 1280px, stacked below 1024px. */}
          <div
            id="evidence-sheet"
            className={cn(
              "border-t border-border lg:fixed lg:inset-y-0 lg:right-0 lg:z-30 lg:w-[400px] lg:overflow-y-auto lg:border-t-0 lg:border-l lg:bg-bg lg:transition-[translate,visibility] lg:duration-(--duration-spatial) lg:ease-out motion-reduce:transition-none",
              sheetOpen ? "lg:visible lg:translate-x-0" : "lg:invisible lg:translate-x-full",
              "xl:visible xl:static xl:z-auto xl:w-auto xl:min-h-0 xl:translate-x-0 xl:transition-none",
            )}
          >
            <div className="hidden justify-end px-4 pt-3 lg:flex xl:hidden">
              <button
                type="button"
                onClick={() => setSheetOpen(false)}
                aria-label="Close the evidence"
                className="inline-flex size-7 items-center justify-center rounded-sm text-text-muted hover:bg-surface-3 hover:text-text focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                <X className="size-4" aria-hidden />
              </button>
            </div>
            <EvidencePanel ask={ask} highlighted={highlighted} onInspect={inspect} onTimeline={openTimeline} />
          </div>
        </div>
      )}

      <AskPalette
        open={paletteOpen}
        recent={recent}
        conflicts={conflicts ?? []}
        onAsk={(text) => {
          setPaletteOpen(false);
          void ask_(text);
        }}
        onConflict={(group) => {
          setPaletteOpen(false);
          openTimeline(group);
        }}
        onClose={() => setPaletteOpen(false)}
      />

      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
    </div>
  );
}
