import { test, describe } from "node:test";
import assert from "node:assert";
import { ApiClient } from "../src/lib/api";

describe("ApiClient: Core utilities & contract", () => {
  test("initializes with default or custom base URL and token management", () => {
    const client = new ApiClient("http://localhost:8000/api/v1");
    assert.strictEqual(client.getToken(), null);

    client.setToken("test-jwt-token");
    assert.strictEqual(client.getToken(), "test-jwt-token");

    client.clearToken();
    assert.strictEqual(client.getToken(), null);
  });

  test("computes correct headers with Authorization and Content-Type", async () => {
    const client = new ApiClient("http://localhost:8000/api/v1");
    client.setToken("bearer-secret-xyz");

    // Mock fetch
    const originalFetch = globalThis.fetch;
    try {
      let interceptedHeaders: any = null;
      let interceptedUrl = "";

      globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
        interceptedUrl = input.toString();
        interceptedHeaders = init?.headers;
        return {
          ok: true,
          status: 200,
          json: async () => ({ status: "ok", version: "1.0.0" }),
        } as Response;
      }) as any;

      const health = await client.getHealthReady();
      assert.strictEqual(health.status, "ok");
      assert.match(interceptedUrl, /\/health\/ready/);
      assert.strictEqual(interceptedHeaders["Authorization"], "Bearer bearer-secret-xyz");
      assert.strictEqual(interceptedHeaders["Content-Type"], "application/json");
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test("throws descriptive error when API returns non-200 HTTP status", async () => {
    const client = new ApiClient("http://localhost:8000/api/v1");

    const originalFetch = globalThis.fetch;
    try {
      globalThis.fetch = (async () => {
        return {
          ok: false,
          status: 404,
          json: async () => ({ detail: "Document doc-404 not found" }),
        } as Response;
      }) as any;

      await assert.rejects(
        async () => {
          await client.getDocument("ws-1", "doc-404");
        },
        {
          name: "Error",
          message: "Document doc-404 not found",
        }
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});
