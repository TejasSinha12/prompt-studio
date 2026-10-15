// Same-origin proxy from the browser to the local FastAPI backend.
//
// * Only loopback Host headers are accepted (DNS-rebinding defence; the
//   backend's own Host check would otherwise be bypassed by this proxy).
// * The optional API token is added here, server-side, and never reaches the browser.
// * Client aborts propagate to the backend request.
import type { NextRequest } from "next/server";

const BACKEND = process.env.PROMPT_STUDIO_API_URL ?? "http://127.0.0.1:8000";
const TOKEN = process.env.PROMPT_STUDIO_API_TOKEN;
const LOOPBACK = new Set(["127.0.0.1", "localhost", "[::1]"]);
const FORWARD_REQUEST_HEADERS = ["content-type", "x-prompt-studio", "origin", "accept"];
const FORWARD_RESPONSE_HEADERS = ["content-type", "content-disposition"];

export const dynamic = "force-dynamic";

function hostName(host: string | null): string {
  if (!host) return "";
  const h = host.toLowerCase();
  if (h.startsWith("[")) return h.slice(0, h.indexOf("]") + 1);
  return h.split(":")[0] ?? "";
}

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  if (!LOOPBACK.has(hostName(req.headers.get("host")))) {
    return Response.json({ error: { code: "untrusted_host", message: "Use a loopback address." } }, { status: 400 });
  }
  const { path } = await ctx.params;
  if (path.some((seg) => seg === ".." || seg.includes("/"))) {
    return Response.json({ error: { code: "bad_request", message: "Invalid path." } }, { status: 400 });
  }
  const url = `${BACKEND}/api/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const headers = new Headers();
  for (const h of FORWARD_REQUEST_HEADERS) {
    const v = req.headers.get(h);
    if (v) headers.set(h, v);
  }
  if (TOKEN) headers.set("authorization", `Bearer ${TOKEN}`);
  const hasBody = !["GET", "HEAD"].includes(req.method);
  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: req.method,
      headers,
      body: hasBody ? await req.arrayBuffer() : undefined,
      signal: req.signal,
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    return Response.json(
      { error: { code: "backend_unavailable", message: `The backend at ${BACKEND} is not reachable. Start it with "npm run dev".` } },
      { status: 502 },
    );
  }
  const outHeaders = new Headers({ "cache-control": "no-store" });
  for (const h of FORWARD_RESPONSE_HEADERS) {
    const v = upstream.headers.get(h);
    if (v) outHeaders.set(h, v);
  }
  return new Response(upstream.status === 204 ? null : upstream.body, { status: upstream.status, headers: outHeaders });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };
