/**
 * The one API client. Every response is validated against the SRS §3 shapes, and every failure becomes
 * an `ApiError` carrying the `request_id` when the API sent one, so the UI can show it.
 */
import { z } from "zod";

const REQUEST_TIMEOUT_MS = 30_000;

export const DOCUMENT_STATUSES = [
  "pending",
  "queued",
  "parsing",
  "indexing",
  "ready",
  "failed",
  "duplicate",
] as const;

const DocumentStatus = z.enum(DOCUMENT_STATUSES);

export const DocumentSchema = z.object({
  document_id: z.string().min(1),
  workspace_id: z.string().min(1),
  filename: z.string(),
  content_type: z.string(),
  size_bytes: z.number().int().nonnegative(),
  status: DocumentStatus,
  stage: DocumentStatus,
  uploaded_at: z.string(),
  checksum: z.string().nullish(),
  error: z.string().nullish(),
  duplicate_of: z.string().nullish(),
  chunk_count: z.number().int().nonnegative().nullish(),
  version_label: z.string().nullish(),
  source_timestamp: z.string().nullish(),
});

export const EvidenceSchema = z.object({
  evidence_id: z.string().min(1),
  chunk_id: z.string().min(1),
  document_id: z.string().min(1),
  filename: z.string().nullish(),
  quoted_span: z.string(),
  page_or_section: z.string().nullish(),
  char_start: z.number().int().nonnegative(),
  char_end: z.number().int().nonnegative(),
  version_label: z.string().nullish(),
  source_timestamp: z.string().nullish(),
  retrieval_rank: z.number().int().positive(),
  retrieval_score: z.number(),
});

const RequestId = z.string().min(1);

const WorkspaceResponse = z.object({
  request_id: RequestId,
  workspace: z.object({ workspace_id: z.string().min(1), created_at: z.string() }),
});

const UploadUrlResponse = z.object({
  request_id: RequestId,
  document: DocumentSchema,
  upload: z.object({ url: z.url(), fields: z.record(z.string(), z.string()) }),
  expires_in: z.number().int().positive(),
});

const CompleteResponse = z.object({
  request_id: RequestId,
  document: DocumentSchema,
  duplicate: z.boolean(),
});

const DocumentsResponse = z.object({
  request_id: RequestId,
  documents: z.array(DocumentSchema),
});

const QueryResponse = z.object({
  request_id: RequestId,
  query_id: z.string().min(1),
  status: z.enum(["retrieved", "insufficient_evidence"]),
  evidence: z.array(EvidenceSchema),
  conflicts: z.array(z.unknown()),
});

export const ANSWER_STATUSES = ["grounded", "partial", "insufficient_evidence"] as const;

const AnswerResponse = z.object({
  request_id: RequestId,
  query_id: z.string().min(1),
  status: z.enum(ANSWER_STATUSES),
  answer: z.string(),
  claims: z.array(z.object({ text: z.string().min(1), evidence_ids: z.array(z.string().min(1)).min(1) })),
  answer_provider: z.string().nullable(),
  model_id: z.string().nullable(),
});

const ProvidersSchema = z.object({
  environment: z.string().min(1),
  answer_provider: z.string().min(1),
  answer_model: z.string().nullable(),
  embedding_provider: z.string().min(1),
  embedding_model: z.string().min(1),
  embedding_version: z.string().min(1),
});

const HealthResponse = z.object({
  request_id: RequestId,
  status: z.enum(["ok", "degraded"]),
  dependencies: z.record(z.string(), z.string()),
  // Absent only when the configuration itself failed to load.
  providers: ProvidersSchema.optional(),
});

const ErrorEnvelope = z.object({
  error: z.object({ code: z.string(), message: z.string(), request_id: z.string().nullish() }),
});

export type DocumentRecord = z.infer<typeof DocumentSchema>;
export type DocumentStatus = z.infer<typeof DocumentStatus>;
export type Evidence = z.infer<typeof EvidenceSchema>;
export type UploadTicket = z.infer<typeof UploadUrlResponse>;
export type Completion = z.infer<typeof CompleteResponse>;
export type QueryResult = z.infer<typeof QueryResponse>;
export type AnswerResult = z.infer<typeof AnswerResponse>;
export type Health = z.infer<typeof HealthResponse>;
export type Providers = z.infer<typeof ProvidersSchema>;

export class ApiError extends Error {
  readonly status: number | null;
  readonly code: string;
  readonly requestId: string | null;

  constructor(options: {
    status: number | null;
    code: string;
    message: string;
    requestId: string | null;
  }) {
    super(options.message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.requestId = options.requestId;
  }
}

/** Anything thrown that isn't already an `ApiError` is a bug in the page, not an API failure. */
export function asApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  return new ApiError({
    status: null,
    code: "unexpected",
    message: "Something went wrong in the page. Reload it and try again.",
    requestId: null,
  });
}

type Fetch = (input: string, init?: RequestInit) => Promise<Response>;

export function createApiClient(options: { baseUrl: string | undefined; fetch?: Fetch }) {
  const baseUrl = options.baseUrl?.replace(/\/+$/, "") ?? "";
  const doFetch: Fetch = options.fetch ?? ((input, init) => fetch(input, init));

  async function call<T>(
    schema: z.ZodType<T>,
    method: "GET" | "POST",
    path: string,
    body?: unknown,
    // Statuses whose body is a normal response, not an error envelope (a degraded /health is 503).
    acceptStatuses: readonly number[] = [],
  ): Promise<T> {
    if (!baseUrl) {
      throw new ApiError({
        status: null,
        code: "not_configured",
        message: "This build has no API address. Set NEXT_PUBLIC_API_URL and rebuild.",
        requestId: null,
      });
    }

    let response: Response;
    try {
      response = await doFetch(`${baseUrl}${path}`, {
        method,
        headers: body === undefined ? undefined : { "content-type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
    } catch (cause) {
      const timedOut = cause instanceof DOMException && cause.name === "TimeoutError";
      throw new ApiError({
        status: null,
        code: timedOut ? "timeout" : "network",
        message: timedOut
          ? "The API took too long to respond. Retry in a moment."
          : "Couldn't reach the API. Check your connection, then retry.",
        requestId: null,
      });
    }

    const headerRequestId = response.headers.get("x-request-id");
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = undefined;
    }

    if (!response.ok && !acceptStatuses.includes(response.status)) {
      const envelope = ErrorEnvelope.safeParse(payload);
      if (envelope.success) {
        throw new ApiError({
          status: response.status,
          code: envelope.data.error.code,
          message: envelope.data.error.message,
          requestId: envelope.data.error.request_id ?? headerRequestId,
        });
      }
      throw new ApiError({
        status: response.status,
        code: "unexpected_response",
        message: `The API returned an unexpected error (HTTP ${response.status}). Retry, and quote the request ID if it keeps failing.`,
        requestId: headerRequestId,
      });
    }

    const parsed = schema.safeParse(payload);
    if (!parsed.success) {
      const bodyRequestId = z.object({ request_id: RequestId }).safeParse(payload);
      throw new ApiError({
        status: response.status,
        code: "invalid_response",
        message:
          "The API sent a response this page doesn't recognise. Reload the page, and quote the request ID if it keeps happening.",
        requestId: bodyRequestId.success ? bodyRequestId.data.request_id : headerRequestId,
      });
    }
    return parsed.data;
  }

  const ws = (workspaceId: string) => `/workspaces/${encodeURIComponent(workspaceId)}`;

  return {
    createWorkspace: () => call(WorkspaceResponse, "POST", "/workspaces"),

    createUploadUrl: (workspaceId: string, file: { filename: string; size_bytes: number }) =>
      call(UploadUrlResponse, "POST", `${ws(workspaceId)}/documents/upload-url`, file),

    completeUpload: (workspaceId: string, documentId: string) =>
      call(
        CompleteResponse,
        "POST",
        `${ws(workspaceId)}/documents/${encodeURIComponent(documentId)}/complete`,
      ),

    listDocuments: (workspaceId: string) =>
      call(DocumentsResponse, "GET", `${ws(workspaceId)}/documents`),

    query: (workspaceId: string, question: string) =>
      call(QueryResponse, "POST", `${ws(workspaceId)}/query`, { question }),

    answer: (workspaceId: string, queryId: string) =>
      call(
        AnswerResponse,
        "POST",
        `${ws(workspaceId)}/queries/${encodeURIComponent(queryId)}/answer`,
      ),

    health: () => call(HealthResponse, "GET", "/health", undefined, [503]),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;

export const api = createApiClient({ baseUrl: process.env.NEXT_PUBLIC_API_URL });

/**
 * Sends the file to S3 with the pre-signed POST. XMLHttpRequest rather than fetch, because only XHR
 * reports upload progress. S3 requires the file to be the last form field.
 */
export function uploadToS3(
  upload: UploadTicket["upload"],
  file: File,
  onProgress: (fraction: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    for (const [name, value] of Object.entries(upload.fields)) form.append(name, value);
    form.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", upload.url);
    xhr.timeout = 120_000;
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    const fail = (message: string) =>
      reject(new ApiError({ status: xhr.status || null, code: "upload_failed", message, requestId: null }));
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress(1);
        resolve();
      } else if (xhr.status === 400 && xhr.responseText.includes("EntityTooLarge")) {
        fail("Storage rejected the file as too large. Upload a smaller file.");
      } else if (xhr.status === 403) {
        fail("The upload link expired or was refused. Upload the file again.");
      } else {
        fail(`Storage rejected the upload (HTTP ${xhr.status}). Upload the file again.`);
      }
    };
    xhr.onerror = () => fail("The upload was interrupted. Check your connection, then upload again.");
    xhr.ontimeout = () => fail("The upload took too long. Check your connection, then upload again.");
    xhr.send(form);
  });
}
