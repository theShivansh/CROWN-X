"use client";

import {
  CheckCircle,
  CircleNotch,
  Copy,
  UploadSimple,
  WarningOctagon,
  X,
} from "@phosphor-icons/react";
import { useRef, useState, type DragEvent, type ReactNode } from "react";

import { ErrorNotice } from "@/components/error-notice";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { ApiError, DocumentRecord } from "@/lib/api";
import { cn } from "@/lib/utils";

import type { LocalUpload } from "./use-documents";

const ACCEPT = ".md,.txt,.pdf";

export function DocumentsRail(props: {
  documents: DocumentRecord[] | null;
  loadError: ApiError | null;
  uploads: LocalUpload[];
  onUpload: (files: Iterable<File>) => void;
  onDismissUpload: (key: string) => void;
  onRetryLoad: () => void;
}) {
  const { documents, loadError, uploads, onUpload, onDismissUpload, onRetryLoad } = props;
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const byId = new Map((documents ?? []).map((d) => [d.document_id, d]));
  const uploadingIds = new Set(uploads.map((u) => u.documentId));
  // A document still `pending` that this page isn't uploading is an abandoned upload: hide it.
  const shown = [...(documents ?? [])]
    .filter((d) => !uploadingIds.has(d.document_id) && d.status !== "pending")
    .sort((a, b) => b.uploaded_at.localeCompare(a.uploaded_at));

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    if (event.dataTransfer.files.length) onUpload(event.dataTransfer.files);
  }

  return (
    <nav aria-label="Documents" className="flex min-h-0 flex-col gap-4 p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-medium text-text">Documents</h2>
        {documents ? (
          <span className="font-mono text-xs tabular-nums text-text-subtle">
            {documents.filter((d) => d.status === "ready").length} ready
          </span>
        ) : null}
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex flex-col items-start gap-2 rounded-md border border-dashed border-border-strong p-3 transition-colors duration-(--duration-fast) ease-out",
          dragging && "border-accent bg-accent-soft",
        )}
      >
        <Button variant="outline" onClick={() => input.current?.click()}>
          <UploadSimple data-icon="inline-start" />
          Upload files
        </Button>
        <p className="text-xs text-text-muted">Drop files here. Markdown, plain text or PDF, up to 5 MB each.</p>
        <input
          ref={input}
          type="file"
          accept={ACCEPT}
          multiple
          className="sr-only"
          tabIndex={-1}
          aria-hidden
          onChange={(e) => {
            if (e.target.files?.length) onUpload(Array.from(e.target.files));
            e.target.value = "";
          }}
        />
      </div>

      {loadError ? (
        <ErrorNotice
          error={loadError}
          action={
            <Button size="sm" variant="outline" onClick={onRetryLoad}>
              Retry
            </Button>
          }
        />
      ) : null}

      <ul className="flex min-h-0 flex-col gap-2 overflow-y-auto" aria-live="polite">
        {uploads.map((u) => (
          <UploadCard key={u.key} upload={u} onDismiss={() => onDismissUpload(u.key)} />
        ))}
        {shown.map((d) => (
          <DocumentCard
            key={d.document_id}
            document={d}
            original={d.duplicate_of ? byId.get(d.duplicate_of) : undefined}
          />
        ))}
        {documents === null && !loadError ? (
          <li className="flex flex-col gap-2" aria-label="Loading documents">
            <Skeleton className="h-14 rounded-md bg-surface-2" />
            <Skeleton className="h-14 rounded-md bg-surface-2" />
          </li>
        ) : null}
        {documents?.length === 0 && uploads.length === 0 ? (
          <li className="text-sm text-text-muted">
            Upload two or more versions of a project document to see where they disagree.
          </li>
        ) : null}
      </ul>
    </nav>
  );
}

function Card({ title, status, children }: { title: string; status: ReactNode; children?: ReactNode }) {
  return (
    <li className="flex flex-col gap-1.5 rounded-md border border-border bg-surface p-3">
      <p className="truncate text-dense font-medium text-text" title={title}>
        {title}
      </p>
      <div className="flex items-center gap-1.5 text-xs text-text-muted">{status}</div>
      {children}
    </li>
  );
}

const Working = ({ label }: { label: string }) => (
  <>
    <CircleNotch className="size-3.5 animate-spin motion-reduce:animate-none" aria-hidden />
    <span>{label}</span>
  </>
);

function UploadCard({ upload, onDismiss }: { upload: LocalUpload; onDismiss: () => void }) {
  if (upload.phase === "failed" && upload.error) {
    return (
      <Card
        title={upload.filename}
        status={
          <>
            <WarningOctagon weight="bold" className="size-3.5 text-error" aria-hidden />
            <span className="text-error">Upload failed</span>
            <Button
              variant="ghost"
              size="icon-xs"
              className="ml-auto"
              onClick={onDismiss}
              aria-label={`Dismiss ${upload.filename}`}
            >
              <X />
            </Button>
          </>
        }
      >
        <p className="text-xs text-text">{upload.error.message}</p>
        {upload.error.requestId ? (
          <p className="font-mono text-xs break-all text-text-subtle">{upload.error.requestId}</p>
        ) : null}
      </Card>
    );
  }
  const percent = Math.round(upload.progress * 100);
  const label =
    upload.phase === "requesting"
      ? "Preparing upload"
      : upload.phase === "uploading"
        ? `Uploading ${percent}%`
        : "Checking the stored file";
  return (
    <Card title={upload.filename} status={<Working label={label} />}>
      <div className="h-1 overflow-hidden rounded-sm bg-surface-3" aria-hidden>
        <div
          className="h-full origin-left bg-accent transition-transform duration-(--duration-base) ease-out"
          style={{ transform: `scaleX(${upload.progress})` }}
        />
      </div>
    </Card>
  );
}

function DocumentCard({ document: d, original }: { document: DocumentRecord; original?: DocumentRecord }) {
  switch (d.status) {
    case "queued":
      return <Card title={d.filename} status={<Working label="Queued for parsing" />} />;
    case "parsing":
      return <Card title={d.filename} status={<Working label={`Parsing ${d.filename}`} />} />;
    case "indexing":
      return <Card title={d.filename} status={<Working label="Indexing passages" />} />;
    case "ready":
      return (
        <Card
          title={d.filename}
          status={
            <>
              <CheckCircle className="size-3.5" aria-hidden />
              <span>
                Ready · <span className="font-mono tabular-nums">{d.chunk_count ?? 0}</span>{" "}
                {d.chunk_count === 1 ? "passage" : "passages"}
              </span>
            </>
          }
        />
      );
    case "failed":
      return (
        <Card
          title={d.filename}
          status={
            <>
              <WarningOctagon weight="bold" className="size-3.5 text-error" aria-hidden />
              <span className="text-error">Ingestion failed</span>
            </>
          }
        >
          <p className="text-xs text-text">{d.error ?? "Ingestion stopped without a reason. Upload the file again."}</p>
        </Card>
      );
    case "duplicate":
      return (
        <Card
          title={d.filename}
          status={
            <>
              <Copy className="size-3.5" aria-hidden />
              <span>Already indexed as {original?.filename ?? "an earlier upload"}</span>
            </>
          }
        />
      );
    default:
      return null;
  }
}
