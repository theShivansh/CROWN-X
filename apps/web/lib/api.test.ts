import { describe, expect, it } from "vitest";

import { ApiError, createApiClient } from "./api";

const WS = "ws_abcdefghijklmnopqrstuv";

function respond(status: number, body: unknown, headers: Record<string, string> = {}) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const fetch = async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    const text = typeof body === "string" ? body : JSON.stringify(body);
    return new Response(text, { status, headers: { "content-type": "application/json", ...headers } });
  };
  return { client: createApiClient({ baseUrl: "https://api.example.test/", fetch }), calls };
}

async function caught(promise: Promise<unknown>): Promise<ApiError> {
  const error = await promise.then(
    () => null,
    (e: unknown) => e,
  );
  expect(error).toBeInstanceOf(ApiError);
  return error as ApiError;
}

const evidence = {
  evidence_id: "ev_1",
  chunk_id: "doc_x:0",
  document_id: "doc_x",
  filename: "SCENARIO.md",
  quoted_span: "Submissions close on 20 September.",
  page_or_section: "Deadline",
  char_start: 0,
  char_end: 34,
  version_label: null,
  source_timestamp: null,
  retrieval_rank: 1,
  retrieval_score: 0.032787,
};

describe("api client", () => {
  it("returns a validated query result", async () => {
    const { client, calls } = respond(200, {
      request_id: "req_1",
      query_id: "qry_1",
      status: "retrieved",
      evidence: [evidence],
      conflicts: [],
    });
    const result = await client.query(WS, "What is the submission deadline?");
    expect(result.evidence[0].chunk_id).toBe("doc_x:0");
    expect(calls[0].url).toBe(`https://api.example.test/workspaces/${WS}/query`);
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({
      question: "What is the submission deadline?",
    });
  });

  it("rejects a malformed response and keeps its request_id", async () => {
    const { client } = respond(200, {
      request_id: "req_malformed",
      query_id: "qry_1",
      status: "retrieved",
      evidence: [{ ...evidence, chunk_id: 42 }],
      conflicts: [],
    });
    const error = await caught(client.query(WS, "What is the submission deadline?"));
    expect(error.code).toBe("invalid_response");
    expect(error.requestId).toBe("req_malformed");
  });

  it("rejects an unknown status value", async () => {
    const { client } = respond(200, { request_id: "req_2", documents: [{ status: "done" }] });
    const error = await caught(client.listDocuments(WS));
    expect(error.code).toBe("invalid_response");
  });

  it("surfaces the error envelope's code, message and request_id", async () => {
    const { client } = respond(
      413,
      {
        error: {
          code: "too_large",
          message: "The file is 9,000,000 bytes; the limit is 5,242,880 bytes.",
          request_id: "req_413",
        },
      },
      { "x-request-id": "req_header" },
    );
    const error = await caught(client.createUploadUrl(WS, { filename: "big.md", size_bytes: 9_000_000 }));
    expect(error.status).toBe(413);
    expect(error.code).toBe("too_large");
    expect(error.message).toContain("5,242,880");
    expect(error.requestId).toBe("req_413");
  });

  it("falls back to the x-request-id header when the error body isn't an envelope", async () => {
    const { client } = respond(502, "Bad Gateway", { "x-request-id": "req_gateway" });
    const error = await caught(client.listDocuments(WS));
    expect(error.code).toBe("unexpected_response");
    expect(error.requestId).toBe("req_gateway");
  });

  it("reports a network failure without inventing a request_id", async () => {
    const client = createApiClient({
      baseUrl: "https://api.example.test",
      fetch: async () => {
        throw new TypeError("Failed to fetch");
      },
    });
    const error = await caught(client.createWorkspace());
    expect(error.code).toBe("network");
    expect(error.requestId).toBeNull();
  });

  it("refuses to call anything when no API address is configured", async () => {
    const client = createApiClient({ baseUrl: undefined, fetch: async () => new Response("{}") });
    const error = await caught(client.createWorkspace());
    expect(error.code).toBe("not_configured");
  });

  it("encodes path segments", async () => {
    const { client, calls } = respond(200, { request_id: "req_3", documents: [] });
    await client.listDocuments("ws/../other");
    expect(calls[0].url).toBe("https://api.example.test/workspaces/ws%2F..%2Fother/documents");
  });

  it("returns a validated answer and calls the stored query's answer route", async () => {
    const { client, calls } = respond(200, {
      request_id: "req_a",
      query_id: "qry_abc",
      status: "partial",
      answer: "Submissions close on 22 September.",
      claims: [{ text: "Submissions close on 22 September.", evidence_ids: ["ev_1"] }],
      answer_provider: "mock",
      model_id: "mock-extractive",
    });
    const result = await client.answer(WS, "qry_abc");
    expect(result.status).toBe("partial");
    expect(calls[0].url).toBe(`https://api.example.test/workspaces/${WS}/queries/qry_abc/answer`);
    expect(calls[0].init?.method).toBe("POST");
  });

  it("rejects an answer whose claim cites nothing", async () => {
    const { client } = respond(200, {
      request_id: "req_b",
      query_id: "qry_abc",
      status: "grounded",
      answer: "x",
      claims: [{ text: "x", evidence_ids: [] }],
      answer_provider: "bedrock",
      model_id: "m",
    });
    const error = await caught(client.answer(WS, "qry_abc"));
    expect(error.code).toBe("invalid_response");
    expect(error.requestId).toBe("req_b");
  });

  it("reads a degraded /health (503) as a normal response with its providers", async () => {
    const { client } = respond(503, {
      request_id: "req_h",
      status: "degraded",
      dependencies: { config: "ok", index: "unreachable" },
      providers: {
        environment: "production",
        answer_provider: "none",
        answer_model: null,
        embedding_provider: "bedrock",
        embedding_model: "amazon.titan-embed-text-v2:0",
        embedding_version: "1",
      },
    });
    const health = await client.health();
    expect(health.status).toBe("degraded");
    expect(health.providers?.environment).toBe("production");
  });
});
