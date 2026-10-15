import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, errorMessage, qs } from "@/lib/api";

afterEach(() => vi.restoreAllMocks());

describe("api client", () => {
  it("sends the CSRF header on every request and JSON bodies on mutations", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ ok: 1 }), { status: 200 }));
    await api.post("/api/x", { a: 1 });
    const [, init] = f.mock.calls[0]!;
    expect((init!.headers as Record<string, string>)["X-Prompt-Studio"]).toBe("1");
    expect(init!.body).toBe('{"a":1}');
  });

  it("maps error envelopes to ApiError", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "conflict", message: "Changed elsewhere", details: { current_revision: 3 } } }), { status: 409 }),
    );
    const e = await api.patch("/api/p", {}).catch((x: unknown) => x);
    expect(e).toBeInstanceOf(ApiError);
    expect(e).toMatchObject({ status: 409, code: "conflict", message: "Changed elsewhere", details: { current_revision: 3 } });
  });

  it("reports an unreachable backend clearly", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("fetch failed"));
    const e = await api.get("/api/x").catch((x: unknown) => x);
    expect(errorMessage(e)).toMatch(/Cannot reach the Prompt Studio backend/);
  });

  it("handles non-JSON error bodies", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("<html>bad gateway</html>", { status: 502 }));
    await expect(api.get("/api/x")).rejects.toMatchObject({ status: 502, code: "http_error" });
  });

  it("builds query strings without empty values", () => {
    expect(qs({ q: "a b", tag: "", n: 0, x: undefined, f: false })).toBe("?q=a+b&n=0&f=false");
  });
});
