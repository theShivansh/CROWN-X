"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  api,
  asApiError,
  uploadToS3,
  type ApiError,
  type DocumentRecord,
  type DocumentStatus,
} from "@/lib/api";

const POLL_INTERVAL_MS = 1_500;
const IN_PROGRESS: ReadonlySet<DocumentStatus> = new Set(["queued", "parsing", "indexing"]);

/** A file between choosing it and the API confirming it; after that the document list takes over. */
export type LocalUpload = {
  key: string;
  filename: string;
  phase: "requesting" | "uploading" | "confirming" | "failed";
  progress: number;
  documentId: string | null;
  error: ApiError | null;
};

export function useDocuments(workspaceId: string) {
  const [documents, setDocuments] = useState<DocumentRecord[] | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [uploads, setUploads] = useState<LocalUpload[]>([]);
  const nextKey = useRef(0);

  const refresh = useCallback(async () => {
    try {
      const { documents: latest } = await api.listDocuments(workspaceId);
      setDocuments(latest);
      setLoadError(null);
    } catch (error) {
      setLoadError(asApiError(error));
    }
  }, [workspaceId]);

  useEffect(() => {
    // Initial load; the polling effect below takes over while anything is in progress.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  const needsPolling =
    uploads.some((u) => u.phase === "confirming") ||
    (documents ?? []).some((d) => IN_PROGRESS.has(d.status));

  useEffect(() => {
    if (!needsPolling) return;
    const timer = window.setInterval(() => void refresh(), POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [needsPolling, refresh]);

  const patch = useCallback((key: string, change: Partial<LocalUpload>) => {
    setUploads((all) => all.map((u) => (u.key === key ? { ...u, ...change } : u)));
  }, []);

  const uploadOne = useCallback(
    async (file: File) => {
      const key = `upload-${nextKey.current++}`;
      setUploads((all) => [
        {
          key,
          filename: file.name,
          phase: "requesting",
          progress: 0,
          documentId: null,
          error: null,
        },
        ...all,
      ]);
      try {
        const ticket = await api.createUploadUrl(workspaceId, {
          filename: file.name,
          size_bytes: file.size,
        });
        patch(key, { phase: "uploading", documentId: ticket.document.document_id });
        await uploadToS3(ticket.upload, file, (progress) => patch(key, { progress }));
        patch(key, { phase: "confirming", progress: 1 });
        await api.completeUpload(workspaceId, ticket.document.document_id);
        await refresh();
        setUploads((all) => all.filter((u) => u.key !== key));
      } catch (error) {
        patch(key, { phase: "failed", error: asApiError(error) });
      }
    },
    [workspaceId, patch, refresh],
  );

  const upload = useCallback(
    (files: Iterable<File>) => {
      for (const file of files) void uploadOne(file);
    },
    [uploadOne],
  );

  const dismissUpload = useCallback((key: string) => {
    setUploads((all) => all.filter((u) => u.key !== key));
  }, []);

  return { documents, loadError, uploads, upload, dismissUpload, refresh };
}
