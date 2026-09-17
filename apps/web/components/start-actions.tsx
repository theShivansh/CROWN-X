"use client";

import { ArrowRight, CircleNotch, Plus } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ErrorNotice } from "@/components/error-notice";
import { Button } from "@/components/ui/button";
import { api, asApiError, type ApiError } from "@/lib/api";

export function StartActions({ demoWorkspaceId }: { demoWorkspaceId?: string }) {
  const router = useRouter();
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  async function createWorkspace() {
    setCreating(true);
    setError(null);
    try {
      const { workspace } = await api.createWorkspace();
      router.push(`/app?ws=${encodeURIComponent(workspace.workspace_id)}`);
    } catch (e) {
      setError(asApiError(e));
      setCreating(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-3">
        {demoWorkspaceId ? (
          <Button asChild size="lg" className="h-11 px-4">
            <Link href={`/app?ws=${encodeURIComponent(demoWorkspaceId)}`}>
              Open demo workspace
              <ArrowRight data-icon="inline-end" />
            </Link>
          </Button>
        ) : null}
        <Button
          size="lg"
          variant={demoWorkspaceId ? "outline" : "default"}
          className="h-11 px-4"
          onClick={createWorkspace}
          disabled={creating}
        >
          {creating ? (
            <CircleNotch data-icon="inline-start" className="animate-spin motion-reduce:animate-none" />
          ) : (
            <Plus data-icon="inline-start" />
          )}
          {creating ? "Creating workspace" : "New workspace"}
        </Button>
      </div>
      <p className="text-xs text-text-subtle">
        A workspace link is its only key for now, so share it only with people who should see its
        documents.
      </p>
      {error ? <ErrorNotice error={error} /> : null}
    </div>
  );
}
