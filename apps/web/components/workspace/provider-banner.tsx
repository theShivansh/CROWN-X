"use client";

import { Info, WarningOctagon } from "@phosphor-icons/react";
import { useEffect, useState } from "react";

import { api, type Providers } from "@/lib/api";

type BannerState =
  | { phase: "loading" }
  | { phase: "ready"; providers: Providers | undefined; degraded: boolean }
  | { phase: "error" };

/**
 * ADR-016: which environment and providers answered. Always visible, so an answer from the mock can
 * never be mistaken for one from a model.
 */
export function ProviderBanner() {
  const [state, setState] = useState<BannerState>({ phase: "loading" });

  useEffect(() => {
    let live = true;
    api.health().then(
      (health) => {
        if (live)
          setState({ phase: "ready", providers: health.providers, degraded: health.status !== "ok" });
      },
      () => {
        if (live) setState({ phase: "error" });
      },
    );
    return () => {
      live = false;
    };
  }, []);

  if (state.phase === "loading") return <span className="font-mono text-xs text-text-subtle">Checking API</span>;
  if (state.phase === "error" || !state.providers) {
    return (
      <span className="flex items-center gap-1.5 text-xs text-error">
        <WarningOctagon weight="bold" className="size-3.5" aria-hidden />
        API status unknown
      </span>
    );
  }

  const { environment, answer_provider, answer_model, embedding_provider } = state.providers;
  const offline = answer_provider === "mock" || embedding_provider === "mock";
  return (
    <div className="flex min-w-0 flex-wrap items-center justify-end gap-x-3 gap-y-1 text-xs">
      {offline ? (
        <span className="flex items-center gap-1.5 text-text">
          <Info weight="bold" className="size-3.5 text-accent" aria-hidden />
          Offline demo: answers are extracted sentences, not written by a model
        </span>
      ) : null}
      {answer_provider === "none" ? (
        <span className="text-text-muted">Answers off: no answer model configured</span>
      ) : null}
      {state.degraded ? <span className="text-error">API degraded</span> : null}
      <span className="font-mono text-text-subtle" title={answer_model ?? undefined}>
        {environment} · answers {answer_provider} · embeddings {embedding_provider}
      </span>
    </div>
  );
}
