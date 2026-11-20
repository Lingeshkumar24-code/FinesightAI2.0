import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, setAuthToken, loadStoredToken, ApiError } from "../lib/api";

describe("api client", () => {
  beforeEach(() => {
    localStorage.clear();
    setAuthToken(null);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("persists the auth token to localStorage", () => {
    setAuthToken("abc123");
    expect(localStorage.getItem("finsight_token")).toBe("abc123");
    expect(loadStoredToken()).toBe("abc123");
  });

  it("clears the stored token when set to null", () => {
    setAuthToken("abc123");
    setAuthToken(null);
    expect(localStorage.getItem("finsight_token")).toBeNull();
  });

  it("attaches the Authorization header once a token is set", async () => {
    setAuthToken("my-token");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ access_token: "x", token_type: "bearer", business_id: "b1" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.login("a@b.com", "pw");

    const [, options] = fetchMock.mock.calls[0];
    const headers = options.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer my-token");
  });

  it("raises ApiError with the server-provided detail message on failure", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid or expired token" }), {
        status: 401,
        statusText: "Unauthorized",
        headers: { "content-type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.login("a@b.com", "pw")).rejects.toMatchObject({
      message: "Invalid or expired token",
      status: 401,
    });
  });

  it("wraps a non-JSON error body without throwing a secondary error", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("Internal Server Error", { status: 500, statusText: "Internal Server Error" })
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.login("a@b.com", "pw")).rejects.toBeInstanceOf(ApiError);
  });
});
