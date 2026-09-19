"use client";

import {
  Article,
  ChartLineUp,
  CheckCircle,
  Copy,
  FlowArrow,
  GitDiff,
  MagnifyingGlass,
  Quotes,
  UploadSimple,
  type Icon,
} from "@phosphor-icons/react";
import { useEffect, useState } from "react";

import { ErrorNotice } from "@/components/error-notice";
import { Button } from "@/components/ui/button";
import { Disclosure } from "@/components/ui/disclosure";
import { Skeleton } from "@/components/ui/skeleton";
import { api, asApiError, type ApiError, type Workflows, type WorkflowSuggestion } from "@/lib/api";
import { lastSeen, stepLabel, timesLabel, topSuggestion, whyDetected } from "@/lib/workflows";

import { WorkflowDetail } from "./workflow-detail";

export const STEP_ICONS: Record<string, Icon> = {
  add_document: UploadSimple,
  ask_question: MagnifyingGlass,
  read_answer: Article,
  open_evidence: Quotes,
  inspect_conflict: GitDiff,
  open_timeline: ChartLineUp,
  copy_answer: Copy,
};

type Load = { state: "loading" } | { state: "error"; error: ApiError } | { state: "ready"; view: Workflows };

/**
 * UI_UX §3.7: the repeated workflow code found in this workspace's own actions. A suggestion only:
 * saving keeps a versioned template, and nothing ever runs by itself. Refreshed after each answer.
 */
export function WorkflowCard({ workspaceId, refreshKey }: { workspaceId: string; refreshKey: number }) {
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [busy, setBusy] = useState<"save" | "dismiss" | null>(null);
  const [actionError, setActionError] = useState<ApiError | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    // Every load mines again and names anything new (once: names are stored), so a routine that
    // finished after the last answer still shows, with its name.
    api
      .refreshWorkflows(workspaceId)
      .then((view) => live && setLoad({ state: "ready", view }))
      .catch((error) => live && setLoad({ state: "error", error: asApiError(error) }));
    return () => {
      live = false;
    };
  }, [workspaceId, refreshKey, attempt]);

  async function act(kind: "save" | "dismiss", suggestion: WorkflowSuggestion, name?: string) {
    setBusy(kind);
    setActionError(null);
    try {
      if (kind === "save") await api.saveWorkflow(workspaceId, suggestion.suggestion_id, name);
      else await api.dismissWorkflow(workspaceId, suggestion.suggestion_id);
      setLoad({ state: "ready", view: await api.workflows(workspaceId) });
    } catch (error) {
      setActionError(asApiError(error));
    } finally {
      setBusy(null);
    }
  }

  const suggestion = load.state === "ready" ? topSuggestion(load.view.suggestions) : null;

  return (
    <section aria-labelledby="workflow-heading" className="flex flex-col gap-2 border-t border-border pt-4">
      <h2 id="workflow-heading" className="flex items-center gap-1.5 text-sm font-medium text-text">
        <FlowArrow weight="bold" className="size-4 text-accent" aria-hidden />
        Workflows
      </h2>
      {load.state === "loading" ? (
        <Skeleton className="h-32 rounded-md bg-surface-2" aria-label="Loading workflows" />
      ) : load.state === "error" ? (
        <ErrorNotice
          error={load.error}
          action={
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setLoad({ state: "loading" });
                setAttempt((n) => n + 1);
              }}
            >
              Retry
            </Button>
          }
        />
      ) : suggestion === null ? (
        <p className="text-xs leading-5 text-text-muted">
          No repeated workflow yet. One appears when the same steps happen 3 times, for example asking, inspecting
          a conflict and copying the answer.
        </p>
      ) : (
        <div className="flex flex-col gap-3 rounded-md border border-border bg-surface p-3">
          <div className="flex flex-col gap-1">
            <p className="text-xs text-text-muted">Repeated workflow detected</p>
            <p className="text-dense font-medium text-text">{suggestion.name}</p>
            {suggestion.description ? <p className="text-xs text-text-muted">{suggestion.description}</p> : null}
          </div>
          <ol aria-label="Steps, in order" className="flex flex-col gap-1">
            {suggestion.steps.map((step, index) => {
              const StepIcon = STEP_ICONS[step] ?? FlowArrow;
              return (
                <li key={`${step}-${index}`} className="flex items-center gap-2 text-xs text-text">
                  <span className="w-4 shrink-0 text-right font-mono tabular-nums text-text-subtle">{index + 1}</span>
                  <StepIcon className="size-3.5 shrink-0 text-text-muted" aria-hidden />
                  {stepLabel(step)}
                </li>
              );
            })}
          </ol>
          <div className="flex flex-wrap gap-1.5">
            <span className="rounded-sm border border-border px-1.5 py-0.5 font-mono text-xs tabular-nums text-text">
              {timesLabel(suggestion.support)}
            </span>
            <span className="rounded-sm border border-border px-1.5 py-0.5 font-mono text-xs tabular-nums text-text-muted">
              last seen {lastSeen(suggestion.recency)}
            </span>
          </div>
          {suggestion.saved_versions.length ? (
            <p className="flex items-center gap-1 text-xs text-grounded">
              <CheckCircle weight="bold" className="size-3.5" aria-hidden />
              Saved as v{suggestion.saved_versions.at(-1)!.version}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => void act("save", suggestion)} disabled={busy !== null}>
              {suggestion.saved_versions.length ? "Save a new version" : "Save workflow"}
            </Button>
            <Button size="sm" variant="outline" onClick={() => void act("dismiss", suggestion)} disabled={busy !== null}>
              Dismiss
            </Button>
          </div>
          {actionError ? <ErrorNotice error={actionError} /> : null}
          <Disclosure label="Why detected?">
            <ul className="flex flex-col gap-1 text-xs leading-5 text-text-muted">
              {whyDetected(suggestion).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </Disclosure>
          <button
            type="button"
            onClick={() => setDetailOpen(true)}
            className="w-fit rounded-sm text-xs text-accent underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            See the events behind it
          </button>
        </div>
      )}
      {suggestion ? (
        // Outside the card's content, so the closed dialog's text never reads as the card's.
        <WorkflowDetail
          open={detailOpen}
          suggestion={suggestion}
          templates={load.state === "ready" ? load.view.templates : []}
          busy={busy === "save"}
          onSave={(name) => void act("save", suggestion, name)}
          onClose={() => setDetailOpen(false)}
        />
      ) : null}
    </section>
  );
}
