import { WarningOctagon } from "@phosphor-icons/react";
import type { ReactNode } from "react";

import type { ApiError } from "@/lib/api";

/** DESIGN.md §7 error state: what failed, the next step, and the request ID to quote. */
export function ErrorNotice({ error, action }: { error: ApiError; action?: ReactNode }) {
  return (
    <div
      role="alert"
      className="flex gap-3 rounded-md border border-error/30 bg-error-soft p-3 text-text"
    >
      <WarningOctagon weight="bold" className="mt-0.5 size-4 shrink-0 text-error" aria-hidden />
      <div className="flex min-w-0 flex-col gap-1">
        <p className="text-sm">{error.message}</p>
        {error.requestId ? (
          <p className="font-mono text-xs text-text-muted">
            Request ID <span className="select-all break-all">{error.requestId}</span>
          </p>
        ) : null}
        {action ? <div className="mt-1">{action}</div> : null}
      </div>
    </div>
  );
}
