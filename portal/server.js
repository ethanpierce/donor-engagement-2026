// Tidepath portal: public forms that post into Roomcord rooms.
// Node 20+, no npm dependencies. Configure with environment variables only.
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import { randomBytes } from "node:crypto";

const ROOT = fileURLToPath(new URL(".", import.meta.url));
const PUBLIC = join(ROOT, "public");

loadDotEnv(join(ROOT, ".env"));

const env = process.env;
const CONFIG = {
  port: Number(env.PORT || 8080),
  apiUrl: (env.ROOMCORD_API_URL || "").replace(/\/+$/, ""),
  token: env.ROOMCORD_BOT_TOKEN || "",
  rateMax: Number(env.RATE_LIMIT_MAX || 10),
  rateWindowMs: Number(env.RATE_LIMIT_WINDOW_SEC || 600) * 1000,
  trustProxy: env.TRUST_PROXY === "1",
  dryRun: env.PORTAL_DRY_RUN === "1",
};

// Each form goes to one room and mentions one specialist agent.
// The agent id is the room binding id that the room member list reports.
const TARGETS = {
  volunteer: {
    room: env.ROOM_VOLUNTEERS_ID,
    agent: env.AGENT_VOLUNTEERS_ID,
    agentName: env.AGENT_VOLUNTEERS_NAME || "Tidepath Volunteers",
  },
  workshop: {
    room: env.ROOM_WORKSHOPS_ID,
    agent: env.AGENT_WORKSHOPS_ID,
    agentName: env.AGENT_WORKSHOPS_NAME || "Tidepath Workshops",
  },
  family: {
    room: env.ROOM_PROGRAMS_ID,
    agent: env.AGENT_PROGRAMS_ID,
    agentName: env.AGENT_PROGRAMS_NAME || "Tidepath Programs",
  },
};
TARGETS.approve = TARGETS.workshop;

const MAX_BODY = 8 * 1024 * 1024; // JSON body, includes an optional base64 photo
const MAX_PHOTO = 5 * 1024 * 1024;
const PHOTO_TYPES = { "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif" };

// ---------- text helpers ----------

// One line, no control characters, no markup, no agent or user mentions.
function clean(value, max = 200) {
  if (value === undefined || value === null) return "";
  let s = String(value)
    .normalize("NFC")
    .replace(/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2060-\u206f]/g, " ")
    .replace(/[<>`*~|[\]]/g, "")
    .replace(/(^|[^\w.])@+/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
  if (s.length > max) s = s.slice(0, max - 1).trimEnd() + "…";
  return s;
}

const isDate = (s) => /^\d{4}-\d{2}-\d{2}$/.test(s) && !Number.isNaN(Date.parse(s));
const isEmail = (s) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(s);
const isPhone = (s) => /^[+()\d\s.-]{7,20}$/.test(s) && s.replace(/\D/g, "").length >= 7;

// ---------- form definitions ----------
// validate(input) returns { errors: {field: code}, fields: {...cleaned} }.
// format(fields) returns the message body without the mention prefix.

const FORMS = {
  volunteer: {
    title: "Volunteer check-in",
    validate(b) {
      const f = {
        name: clean(b.name, 80),
        phone: clean(b.phone, 20),
        date: clean(b.date, 10),
        hours: clean(b.hours, 5),
        met: clean(b.met, 40),
        happened: clean(b.happened, 600),
        urgent: b.urgent === "yes" ? "yes" : "no",
        urgentText: clean(b.urgentText, 300),
      };
      const e = {};
      if (!f.name) e.name = "required";
      if (f.phone && !isPhone(f.phone)) e.phone = "phone";
      if (!isDate(f.date)) e.date = "date";
      const h = Number(f.hours);
      if (!f.hours) e.hours = "required";
      else if (!(h > 0 && h <= 24)) e.hours = "hours";
      else f.hours = String(Math.round(h * 4) / 4);
      if (!f.happened) e.happened = "required";
      if (f.urgent === "yes" && !f.urgentText) e.urgentText = "required";
      return { errors: e, fields: f };
    },
    format(f, extra) {
      const head = ["Portal", "Volunteer check-in", f.name, f.date, `${f.hours}h`];
      if (f.met) head.push(`met ${f.met}`);
      head.push(f.urgent === "yes" ? `urgent: ${f.urgentText}` : "urgent: no");
      const lines = [head.join(" · "), `What happened: ${f.happened}`];
      if (f.phone) lines.push(`Volunteer phone: ${f.phone}`);
      if (extra.photo) lines.push("Photo attached.");
      else if (extra.photoSkipped) lines.push("Photo: upload failed, not attached.");
      return lines.join("\n");
    },
  },

  workshop: {
    title: "Workshop request",
    validate(b) {
      const topics = ["safety", "mental-health", "other"];
      const modes = ["in-person", "online"];
      const f = {
        school: clean(b.school, 120),
        contact: clean(b.contact, 80),
        email: clean(b.email, 120),
        phone: clean(b.phone, 20),
        dates: clean(b.dates, 160),
        grade: clean(b.grade, 30),
        headcount: clean(b.headcount, 4),
        topic: topics.includes(b.topic) ? b.topic : "",
        topicOther: clean(b.topicOther, 120),
        language: clean(b.language, 30),
        mode: modes.includes(b.mode) ? b.mode : "",
        notes: clean(b.notes, 600),
      };
      const e = {};
      for (const k of ["school", "contact", "dates", "grade", "language"]) if (!f[k]) e[k] = "required";
      if (!isEmail(f.email)) e.email = f.email ? "email" : "required";
      if (f.phone && !isPhone(f.phone)) e.phone = "phone";
      const n = Number(f.headcount);
      if (!f.headcount) e.headcount = "required";
      else if (!(Number.isInteger(n) && n > 0 && n <= 2000)) e.headcount = "number";
      if (!f.topic) e.topic = "required";
      if (f.topic === "other" && !f.topicOther) e.topicOther = "required";
      if (!f.mode) e.mode = "required";
      return { errors: e, fields: f };
    },
    format(f) {
      const topic = f.topic === "other" ? `other: ${f.topicOther}` : f.topic.replace("-", " ");
      const head = ["Portal", "Workshop request", f.school, `grade ${f.grade}`, `${f.headcount} students`, topic, f.mode.replace("-", " "), f.language];
      const lines = [
        head.join(" · "),
        `Preferred dates: ${f.dates}`,
        `Contact: ${f.contact} · ${f.email}${f.phone ? " · " + f.phone : ""}`,
      ];
      if (f.notes) lines.push(`Notes: ${f.notes}`);
      return lines.join("\n");
    },
  },

  family: {
    title: "Family sign-up",
    validate(b) {
      const programs = ["mentoring", "family-counseling", "workshops"];
      const f = {
        parent: clean(b.parent, 80),
        phone: clean(b.phone, 20),
        email: clean(b.email, 120),
        language: clean(b.language, 30),
        child: clean(b.child, 60),
        age: clean(b.age, 3),
        school: clean(b.school, 120),
        program: programs.includes(b.program) ? b.program : "",
        consent: b.consent === true || b.consent === "yes" || b.consent === "on",
      };
      const e = {};
      for (const k of ["parent", "language", "child", "school"]) if (!f[k]) e[k] = "required";
      if (!f.phone && !f.email) e.phone = "contact";
      if (f.phone && !isPhone(f.phone)) e.phone = "phone";
      if (f.email && !isEmail(f.email)) e.email = "email";
      const a = Number(f.age);
      if (!f.age) e.age = "required";
      else if (!(Number.isInteger(a) && a >= 3 && a <= 21)) e.age = "age";
      if (!f.program) e.program = "required";
      if (!f.consent) e.consent = "consent";
      return { errors: e, fields: f };
    },
    format(f) {
      const head = ["Portal", "Family sign-up", f.parent, `child ${f.child} (${f.age})`, f.school, f.program.replace("-", " "), `language ${f.language}`];
      const contact = [f.phone, f.email].filter(Boolean).join(" · ");
      return [head.join(" · "), `Contact: ${contact}`, "Consent to contact: yes"].join("\n");
    },
  },

  approve: {
    title: "Slide approval",
    validate(b) {
      const f = {
        request: clean(b.request, 12).toUpperCase(),
        version: clean(b.version, 6).toLowerCase(),
        decision: b.decision === "approve" ? "approve" : b.decision === "changes" ? "changes" : "",
        name: clean(b.name, 80),
        comment: clean(b.comment, 600),
      };
      const e = {};
      if (!/^W\d{3,6}$/.test(f.request)) e.request = "request";
      if (!/^v\d{1,3}$/.test(f.version)) e.version = "version";
      if (!f.decision) e.decision = "required";
      if (f.decision === "changes" && !f.comment) e.comment = "required";
      return { errors: e, fields: f };
    },
    format(f) {
      const by = f.name ? ` (by ${f.name})` : "";
      if (f.decision === "approve") return `School approved ${f.request} ${f.version}${by}. Sent from the Portal.`;
      return `School requested changes to ${f.request} ${f.version}${by}. Sent from the Portal.\nChanges: ${f.comment}`;
    },
  },
};

// ---------- Roomcord client ----------

async function roomcord(method, path, body, headers = {}) {
  const res = await fetch(`${CONFIG.apiUrl}${path}`, {
    method,
    headers: { Authorization: `Bearer ${CONFIG.token}`, ...(body && !(body instanceof FormData) ? { "Content-Type": "application/json" } : {}), ...headers },
    body: body ? (body instanceof FormData ? body : JSON.stringify(body)) : undefined,
    signal: AbortSignal.timeout(15000),
  });
  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : {}; } catch { data = { raw: text.slice(0, 200) }; }
  if (!res.ok) {
    const err = new Error(`Roomcord ${method} ${path.split("?")[0]} -> ${res.status}`);
    err.status = res.status;
    err.detail = data?.error?.message || data?.message || "";
    throw err;
  }
  return data;
}

// The visible @Name must match the agent's display name in the room, so the
// Roomcord API resolves the mention to the agent. Look it up by binding id and
// cache it. Fall back to the configured name when the lookup fails.
const nameCache = new Map();
async function agentName(target) {
  const key = `${target.room}:${target.agent}`;
  const hit = nameCache.get(key);
  if (hit && Date.now() - hit.at < 10 * 60 * 1000) return hit.name;
  let name = target.agentName;
  try {
    const res = await roomcord("GET", `/rooms/${encodeURIComponent(target.room)}/members?limit=200`);
    const m = (res.data || []).find((x) => x.memberType === "agent" && x.agentId === target.agent);
    if (m?.displayName) name = m.displayName;
    else log("warn", "agent not found in room members, using configured name", { room: target.room });
  } catch (err) {
    log("warn", "member lookup failed, using configured name", { error: err.message });
  }
  nameCache.set(key, { name, at: Date.now() });
  return name;
}

async function uploadPhoto(room, photo) {
  const m = /^data:(image\/[a-z]+);base64,([A-Za-z0-9+/=]+)$/.exec(photo || "");
  if (!m || !PHOTO_TYPES[m[1]]) throw Object.assign(new Error("bad photo"), { code: "photo" });
  const buf = Buffer.from(m[2], "base64");
  if (buf.length > MAX_PHOTO) throw Object.assign(new Error("photo too large"), { code: "photoSize" });
  const form = new FormData();
  form.append("image", new Blob([buf], { type: m[1] }), `checkin.${PHOTO_TYPES[m[1]]}`);
  const res = await roomcord("POST", `/rooms/${encodeURIComponent(room)}/images`, form);
  const url = res.url || res.imageUrl || res.data?.url || res.data?.imageUrl;
  if (!url) throw new Error("upload returned no url");
  return url;
}

async function post(formId, fields, photo) {
  const target = TARGETS[formId];
  const extra = {};
  const attachmentUrls = [];
  if (photo) {
    try {
      attachmentUrls.push(await uploadPhoto(target.room, photo));
      extra.photo = true;
    } catch (err) {
      if (err.code) throw err; // the visitor's file is bad: tell them
      log("warn", "photo upload failed, posting without it", { error: err.message });
      extra.photoSkipped = true;
    }
  }
  const text = FORMS[formId].format(fields, extra);
  const name = await agentName(target);
  const body = { content: `@${name} ${text}`, type: "text" };
  if (attachmentUrls.length) body.attachmentUrls = attachmentUrls;
  if (CONFIG.dryRun) {
    log("info", "dry run, not posted", { form: formId, content: body.content });
    return { id: "dry-run" };
  }
  const res = await roomcord("POST", `/rooms/${encodeURIComponent(target.room)}/messages`, body);
  return { id: res.id || res.data?.id || res.message?.id || "" };
}

// ---------- rate limit ----------

const hits = new Map();
function rateLimited(ip) {
  const now = Date.now();
  const list = (hits.get(ip) || []).filter((t) => now - t < CONFIG.rateWindowMs);
  if (list.length >= CONFIG.rateMax) {
    hits.set(ip, list);
    return Math.ceil((CONFIG.rateWindowMs - (now - list[0])) / 1000);
  }
  list.push(now);
  hits.set(ip, list);
  return 0;
}
setInterval(() => {
  const now = Date.now();
  for (const [ip, list] of hits) if (list.every((t) => now - t >= CONFIG.rateWindowMs)) hits.delete(ip);
}, 60000).unref();

function clientIp(req) {
  if (CONFIG.trustProxy) {
    const xff = req.headers["x-forwarded-for"];
    if (xff) return String(xff).split(",")[0].trim();
  }
  return req.socket.remoteAddress || "unknown";
}

// ---------- HTTP ----------

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".webmanifest": "application/manifest+json",
};
const PAGES = { "/": "index.html", "/volunteer": "volunteer.html", "/workshop": "workshop.html", "/family": "family.html", "/approve": "approve.html", "/thanks": "thanks.html" };

const SECURITY_HEADERS = {
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "X-Frame-Options": "DENY",
  "Content-Security-Policy": "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
};

function send(res, status, body, headers = {}) {
  res.writeHead(status, { ...SECURITY_HEADERS, ...headers });
  res.end(body);
}
function json(res, status, data, headers = {}) {
  send(res, status, JSON.stringify(data), { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...headers });
}

async function readJson(req) {
  if (!String(req.headers["content-type"] || "").startsWith("application/json")) throw Object.assign(new Error("json"), { status: 415 });
  let size = 0;
  const chunks = [];
  for await (const c of req) {
    size += c.length;
    if (size > MAX_BODY) throw Object.assign(new Error("too large"), { status: 413 });
    chunks.push(c);
  }
  try {
    const v = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    if (!v || typeof v !== "object" || Array.isArray(v)) throw new Error();
    return v;
  } catch {
    throw Object.assign(new Error("bad json"), { status: 400 });
  }
}

async function handleSubmit(req, res, formId) {
  const form = FORMS[formId];
  if (!form) return json(res, 404, { ok: false, error: "unknown_form" });
  if (!configured(formId)) return json(res, 503, { ok: false, error: "not_configured" });
  const wait = rateLimited(clientIp(req));
  if (wait) return json(res, 429, { ok: false, error: "rate_limited", retryAfter: wait }, { "Retry-After": String(wait) });

  let body;
  try {
    body = await readJson(req);
  } catch (err) {
    return json(res, err.status || 400, { ok: false, error: err.status === 413 ? "too_large" : "bad_request" });
  }
  if (body.website) return json(res, 200, { ok: true, ref: ref() }); // honeypot: pretend success

  const { errors, fields } = form.validate(body);
  if (Object.keys(errors).length) return json(res, 400, { ok: false, error: "invalid", fields: errors });

  const reference = ref();
  try {
    const out = await post(formId, fields, formId === "volunteer" ? body.photo : undefined);
    log("info", "posted", { form: formId, ref: reference, message: out.id });
    return json(res, 200, { ok: true, ref: reference });
  } catch (err) {
    if (err.code) return json(res, 400, { ok: false, error: "invalid", fields: { photo: err.code } });
    log("error", "post failed", { form: formId, ref: reference, error: err.message, detail: err.detail });
    return json(res, 502, { ok: false, error: "upstream" });
  }
}

function configured(formId) {
  const t = TARGETS[formId];
  return Boolean(CONFIG.apiUrl && (CONFIG.token || CONFIG.dryRun) && t?.room && t?.agent);
}

const ref = () => "TP-" + randomBytes(3).toString("hex").toUpperCase();

async function serveStatic(req, res, pathname) {
  const file = PAGES[pathname] || pathname.slice(1);
  const full = normalize(join(PUBLIC, file));
  if (!full.startsWith(PUBLIC)) return send(res, 404, "Not found");
  try {
    const s = await stat(full);
    if (!s.isFile()) throw new Error();
    const type = TYPES[extname(full)] || "application/octet-stream";
    const cache = type.startsWith("text/html") ? "no-cache" : "public, max-age=300";
    send(res, 200, req.method === "HEAD" ? undefined : await readFile(full), { "Content-Type": type, "Cache-Control": cache });
  } catch {
    const page = await readFile(join(PUBLIC, "404.html")).catch(() => "Not found");
    send(res, 404, page, { "Content-Type": "text/html; charset=utf-8" });
  }
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, "http://portal.local");
  try {
    if (url.pathname === "/healthz") return json(res, 200, { ok: true, forms: Object.fromEntries(Object.keys(FORMS).map((f) => [f, configured(f)])) });
    const m = /^\/api\/submit\/([a-z]+)$/.exec(url.pathname);
    if (m) {
      if (req.method !== "POST") return json(res, 405, { ok: false, error: "method" }, { Allow: "POST" });
      return await handleSubmit(req, res, m[1]);
    }
    if (req.method !== "GET" && req.method !== "HEAD") return send(res, 405, "Method not allowed", { Allow: "GET, HEAD" });
    return await serveStatic(req, res, url.pathname);
  } catch (err) {
    log("error", "unhandled", { error: err.message });
    if (!res.headersSent) json(res, 500, { ok: false, error: "server" });
  }
});

function log(level, msg, extra = {}) {
  // Never logs tokens. Form contents are logged only in PORTAL_DRY_RUN mode.
  process.stdout.write(JSON.stringify({ t: new Date().toISOString(), level, msg, ...extra }) + "\n");
}

function loadDotEnv(file) {
  if (!existsSync(file)) return;
  for (const line of readFileSync(file, "utf8").split(/\r?\n/)) {
    const m = /^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/.exec(line);
    if (m && process.env[m[1]] === undefined) process.env[m[1]] = m[2].replace(/^(['"])(.*)\1$/, "$2");
  }
}

export { FORMS, clean };

if (process.argv[1] && fileURLToPath(import.meta.url) === normalize(process.argv[1])) {
  server.listen(CONFIG.port, () => {
    const missing = Object.keys(FORMS).filter((f) => !configured(f));
    log("info", `Tidepath portal on :${CONFIG.port}`, { dryRun: CONFIG.dryRun, notConfigured: missing });
  });
}
