// Tidepath portal on Cloudflare Workers: public forms that post into Roomcord
// rooms. Port of the Go server (server.go, roomcord.go). Config comes from
// Worker vars and secrets with the same names as the Go .env file.
import { FORMS, FORM_ORDER, type Body, type FormId, type Fields, type Extra, decodeBase64Lenient, sliceUnits } from "./forms";
import type { RateLimiter } from "./ratelimit";

export { RateLimiter } from "./ratelimit";

export interface Env {
  ASSETS: Fetcher;
  RATE_LIMITER: DurableObjectNamespace<RateLimiter>;
  ROOMCORD_API_URL?: string;
  ROOMCORD_BOT_TOKEN?: string;
  ROOM_VOLUNTEERS_ID?: string;
  ROOM_WORKSHOPS_ID?: string;
  ROOM_PROGRAMS_ID?: string;
  AGENT_VOLUNTEERS_ID?: string;
  AGENT_WORKSHOPS_ID?: string;
  AGENT_PROGRAMS_ID?: string;
  AGENT_VOLUNTEERS_NAME?: string;
  AGENT_WORKSHOPS_NAME?: string;
  AGENT_PROGRAMS_NAME?: string;
  RATE_LIMIT_MAX?: string;
  RATE_LIMIT_WINDOW_SEC?: string;
  PORTAL_DRY_RUN?: string;
}

type Target = { room?: string; agent?: string; agentName: string };

type Config = {
  apiUrl: string;
  token: string;
  rateMax: number;
  rateWindowMs: number;
  dryRun: boolean;
  targets: Record<FormId, Target>;
};

function config(env: Env): Config {
  const workshop = { room: env.ROOM_WORKSHOPS_ID, agent: env.AGENT_WORKSHOPS_ID, agentName: env.AGENT_WORKSHOPS_NAME || "Tidepath Workshops" };
  return {
    apiUrl: (env.ROOMCORD_API_URL || "").replace(/\/+$/, ""),
    token: env.ROOMCORD_BOT_TOKEN || "",
    rateMax: Number(env.RATE_LIMIT_MAX || 10),
    rateWindowMs: Number(env.RATE_LIMIT_WINDOW_SEC || 600) * 1000,
    dryRun: env.PORTAL_DRY_RUN === "1",
    targets: {
      volunteer: { room: env.ROOM_VOLUNTEERS_ID, agent: env.AGENT_VOLUNTEERS_ID, agentName: env.AGENT_VOLUNTEERS_NAME || "Tidepath Volunteers" },
      workshop,
      family: { room: env.ROOM_PROGRAMS_ID, agent: env.AGENT_PROGRAMS_ID, agentName: env.AGENT_PROGRAMS_NAME || "Tidepath Programs" },
      approve: workshop,
    },
  };
}

const configured = (c: Config, id: FormId) => {
  const t = c.targets[id];
  return Boolean(c.apiUrl && (c.token || c.dryRun) && t.room && t.agent);
};

const MAX_BODY = 8 * 1024 * 1024; // JSON body, includes an optional base64 photo
const MAX_PHOTO = 5 * 1024 * 1024;
const PHOTO_TYPES: Record<string, string> = { "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif" };
const TIMEOUT_MS = 15000; // per outbound Roomcord request

// ---------- logging ----------

// One JSON object per line. Never logs tokens. Form contents are logged only
// in PORTAL_DRY_RUN mode.
function log(level: string, msg: string, extra: Record<string, unknown> = {}) {
  console.log(JSON.stringify({ t: new Date().toISOString(), level, msg, ...extra }));
}

// ---------- Roomcord client ----------

// PhotoError is a problem with the visitor's file. The visitor sees it.
class PhotoError extends Error {
  constructor(readonly code: string) {
    super("bad photo: " + code);
  }
}

class UpstreamError extends Error {
  constructor(message: string, readonly detail: string) {
    super(message);
  }
}

const errMessage = (err: unknown) => (err instanceof Error ? err.message : String(err));

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Json = any;

async function roomcord(c: Config, method: string, path: string, body?: unknown): Promise<Json> {
  const headers: Record<string, string> = { Authorization: `Bearer ${c.token}` };
  let payload: BodyInit | undefined;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(`${c.apiUrl}${path}`, { method, headers, body: payload, signal: AbortSignal.timeout(TIMEOUT_MS) });
  const text = await res.text();
  let data: Json;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { raw: sliceUnits(text, 200) };
  }
  if (!res.ok) {
    const detail = data?.error?.message || data?.message || "";
    throw new UpstreamError(`Roomcord ${method} ${path.split("?")[0]} -> ${res.status}`, String(detail));
  }
  return data;
}

// The visible @Name must match the agent's display name in the room, so
// Roomcord resolves the mention to the agent. Look it up by binding id and
// cache it per isolate for 10 minutes. Fall back to the configured name.
const nameCache = new Map<string, { name: string; at: number }>();

async function agentName(c: Config, t: Target): Promise<string> {
  const key = `${t.room}:${t.agent}`;
  const hit = nameCache.get(key);
  if (hit && Date.now() - hit.at < 10 * 60 * 1000) return hit.name;
  let name = t.agentName;
  try {
    const res = await roomcord(c, "GET", `/rooms/${encodeURIComponent(t.room!)}/members?limit=200`);
    const m = (res.data || []).find((x: Json) => x.memberType === "agent" && x.agentId === t.agent);
    if (m?.displayName) name = String(m.displayName);
    else log("warn", "agent not found in room members, using configured name", { room: t.room });
  } catch (err) {
    log("warn", "member lookup failed, using configured name", { error: errMessage(err) });
  }
  nameCache.set(key, { name, at: Date.now() });
  return name;
}

async function uploadPhoto(c: Config, room: string, photo: unknown): Promise<unknown> {
  const m = /^data:(image\/[a-z]+);base64,([A-Za-z0-9+/=]+)$/.exec(String(photo || ""));
  if (!m || !PHOTO_TYPES[m[1]]) throw new PhotoError("photo");
  const buf = decodeBase64Lenient(m[2]);
  if (buf.length > MAX_PHOTO) throw new PhotoError("photoSize");
  const form = new FormData();
  form.append("image", new Blob([buf], { type: m[1] }), `checkin.${PHOTO_TYPES[m[1]]}`);
  const res = await roomcord(c, "POST", `/rooms/${encodeURIComponent(room)}/images`, form);
  const url = res?.url || res?.imageUrl || res?.data?.url || res?.data?.imageUrl;
  if (!url) throw new Error("upload returned no url");
  return url;
}

// post sends one form to its room. It returns the Roomcord message id.
async function post(c: Config, formId: FormId, fields: Fields, photo: unknown): Promise<string> {
  const t = c.targets[formId];
  const extra: Extra = {};
  const attachmentUrls: unknown[] = [];
  if (photo) {
    try {
      attachmentUrls.push(await uploadPhoto(c, t.room!, photo));
      extra.photo = true;
    } catch (err) {
      if (err instanceof PhotoError) throw err; // the visitor's file is bad: tell them
      log("warn", "photo upload failed, posting without it", { error: errMessage(err) });
      extra.photoSkipped = true;
    }
  }
  const text = FORMS[formId].format(fields, extra);
  const name = await agentName(c, t);
  const body: { content: string; type: string; attachmentUrls?: unknown[] } = { content: `@${name} ${text}`, type: "text" };
  if (attachmentUrls.length) body.attachmentUrls = attachmentUrls;
  if (c.dryRun) {
    log("info", "dry run, not posted", { form: formId, content: body.content });
    return "dry-run";
  }
  const res = await roomcord(c, "POST", `/rooms/${encodeURIComponent(t.room!)}/messages`, body);
  if (res === null) throw new Error("message response is null");
  return String(res.id || res.data?.id || res.message?.id || "");
}

// ---------- HTTP ----------

const TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".webmanifest": "application/manifest+json",
};
const PAGES: Record<string, string> = { "/": "index.html", "/volunteer": "volunteer.html", "/workshop": "workshop.html", "/family": "family.html", "/approve": "approve.html", "/thanks": "thanks.html" };

const SECURITY_HEADERS: Record<string, string> = {
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "X-Frame-Options": "DENY",
  "Content-Security-Policy":
    "default-src 'self'; img-src 'self' data: blob:; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
};

const encoder = new TextEncoder();

// send answers with the security headers. A string body is sent as bytes, so
// the response has no Content-Type unless headers set one (as in Go and Node).
function send(status: number, body: string | BodyInit | null, headers: Record<string, string> = {}): Response {
  const b = typeof body === "string" ? encoder.encode(body) : body;
  return new Response(b, { status, headers: { ...SECURITY_HEADERS, ...headers } });
}

type ApiResponse = { ok: boolean; error?: string; ref?: string; retryAfter?: number; fields?: Record<string, string>; forms?: Record<string, boolean> };

const json = (status: number, data: ApiResponse, headers: Record<string, string> = {}) =>
  send(status, JSON.stringify(data), { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...headers });

function ref(): string {
  const b = crypto.getRandomValues(new Uint8Array(3));
  return "TP-" + Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("").toUpperCase();
}

class StatusError extends Error {
  constructor(readonly status: number) {
    super("status " + status);
  }
}

async function readJson(req: Request): Promise<Body> {
  if (!(req.headers.get("content-type") || "").startsWith("application/json")) throw new StatusError(415);
  let raw: ArrayBuffer;
  try {
    raw = await req.arrayBuffer();
  } catch {
    throw new StatusError(400);
  }
  if (raw.byteLength > MAX_BODY) throw new StatusError(413);
  try {
    const v = JSON.parse(new TextDecoder().decode(raw));
    if (!v || typeof v !== "object" || Array.isArray(v)) throw new Error();
    return v as Body;
  } catch {
    throw new StatusError(400);
  }
}

// Client IP for the rate limit. Cloudflare sets CF-Connecting-IP.
const clientIp = (req: Request) => req.headers.get("CF-Connecting-IP") || "unknown";

async function rateLimited(env: Env, c: Config, ip: string): Promise<number> {
  const stub = env.RATE_LIMITER.get(env.RATE_LIMITER.idFromName(ip));
  return stub.hit(c.rateWindowMs, c.rateMax);
}

async function handleSubmit(req: Request, env: Env, c: Config, id: string): Promise<Response> {
  if (!Object.hasOwn(FORMS, id)) return json(404, { ok: false, error: "unknown_form" });
  const formId = id as FormId;
  if (!configured(c, formId)) return json(503, { ok: false, error: "not_configured" });
  const wait = await rateLimited(env, c, clientIp(req));
  if (wait) return json(429, { ok: false, error: "rate_limited", retryAfter: wait }, { "Retry-After": String(wait) });

  let body: Body;
  try {
    body = await readJson(req);
  } catch (err) {
    const status = err instanceof StatusError ? err.status : 400;
    return json(status, { ok: false, error: status === 413 ? "too_large" : "bad_request" });
  }
  if (body.website) return json(200, { ok: true, ref: ref() }); // honeypot: pretend success

  const { errors, fields } = FORMS[formId].validate(body);
  if (Object.keys(errors).length) return json(400, { ok: false, error: "invalid", fields: errors });

  const reference = ref();
  try {
    const id = await post(c, formId, fields, formId === "volunteer" ? body.photo : undefined);
    log("info", "posted", { form: formId, ref: reference, message: id });
    return json(200, { ok: true, ref: reference });
  } catch (err) {
    if (err instanceof PhotoError) return json(400, { ok: false, error: "invalid", fields: { photo: err.code } });
    log("error", "post failed", { form: formId, ref: reference, error: errMessage(err), ...(err instanceof UpstreamError ? { detail: err.detail } : {}) });
    return json(502, { ok: false, error: "upstream" });
  }
}

// validName is Go's fs.ValidPath plus "no percent sign": the request path is
// still percent-encoded, and no file in public/ has a "%" in its name.
const validName = (name: string) => name !== "" && !name.includes("%") && name.split("/").every((s) => s !== "" && s !== "." && s !== "..");

async function serveStatic(req: Request, env: Env, pathname: string): Promise<Response> {
  const name = PAGES[pathname] || pathname.slice(1);
  if (validName(name)) {
    const res = await env.ASSETS.fetch(new URL("/" + name, req.url));
    if (res.status === 200) {
      const dot = name.lastIndexOf(".");
      const type = (dot > name.lastIndexOf("/") && TYPES[name.slice(dot)]) || "application/octet-stream";
      const cache = type.startsWith("text/html") ? "no-cache" : "public, max-age=300";
      return send(200, res.body, { "Content-Type": type, "Cache-Control": cache });
    }
    await res.body?.cancel();
  }
  const nf = await env.ASSETS.fetch(new URL("/404.html", req.url));
  const page = nf.status === 200 ? nf.body : "Not found";
  return send(404, page, { "Content-Type": "text/html; charset=utf-8" });
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    const c = config(env);
    try {
      if (url.pathname === "/healthz") {
        return json(200, { ok: true, forms: Object.fromEntries(FORM_ORDER.map((f) => [f, configured(c, f)])) });
      }
      const m = /^\/api\/submit\/([a-z]+)$/.exec(url.pathname);
      if (m) {
        if (req.method !== "POST") return json(405, { ok: false, error: "method" }, { Allow: "POST" });
        return await handleSubmit(req, env, c, m[1]);
      }
      if (req.method !== "GET" && req.method !== "HEAD") return send(405, "Method not allowed", { Allow: "GET, HEAD" });
      return await serveStatic(req, env, url.pathname);
    } catch (err) {
      log("error", "unhandled", { error: errMessage(err) });
      return json(500, { ok: false, error: "server" });
    }
  },
} satisfies ExportedHandler<Env>;
