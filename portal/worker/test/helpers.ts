// Test helpers: a mock Roomcord API (same replies and recording as the Go
// mock_test.go) and a Worker started with wrangler's test harness.
import { createServer, type IncomingMessage, type Server } from "node:http";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { createTestHarness, type TestHarness } from "wrangler";

export const roomVolunteers = "11111111-1111-4111-8111-111111111111";
export const roomWorkshops = "22222222-2222-4222-8222-222222222222";
export const roomPrograms = "33333333-3333-4333-8333-333333333333";
export const agentVolunteer = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
export const agentWorkshops = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
export const agentPrograms = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
export const fakeToken = "test-token-not-real";

const roomAgents: Record<string, [string, string]> = {
  [roomVolunteers]: [agentVolunteer, "Volunteers Agent"],
  [roomWorkshops]: [agentWorkshops, "Workshops Agent"],
  [roomPrograms]: [agentPrograms, "Programs Agent"],
};

export type RecordedPart = { contentDisposition: string; contentType: string; size: number; sha256: string };
export type Recorded = { method: string; path: string; headers: Record<string, string>; body?: string; parts?: RecordedPart[] };
export type MockResponse = { status: number; body: string };

export type MockRoomcord = { url: string; requests: Recorded[]; close(): Promise<void>; server: Server };

function readBody(req: IncomingMessage): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on("data", (c: Buffer) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

// parseMultipart returns the raw parts like Go's multipart.Reader.NextRawPart.
function parseMultipart(body: Buffer, boundary: string): RecordedPart[] {
  const parts: RecordedPart[] = [];
  const delim = Buffer.from("--" + boundary);
  let pos = body.indexOf(delim);
  while (pos >= 0) {
    pos += delim.length;
    if (body.subarray(pos, pos + 2).toString() === "--") break;
    pos += 2; // CRLF after the boundary line
    const headerEnd = body.indexOf("\r\n\r\n", pos);
    if (headerEnd < 0) break;
    const headers: Record<string, string> = {};
    for (const line of body.subarray(pos, headerEnd).toString("utf8").split("\r\n")) {
      const i = line.indexOf(":");
      if (i > 0) headers[line.slice(0, i).trim().toLowerCase()] = line.slice(i + 1).trim();
    }
    const next = body.indexOf(Buffer.concat([Buffer.from("\r\n"), delim]), headerEnd + 4);
    if (next < 0) break;
    const data = body.subarray(headerEnd + 4, next);
    parts.push({
      contentDisposition: headers["content-disposition"] ?? "",
      contentType: headers["content-type"] ?? "",
      size: data.length,
      sha256: createHash("sha256").update(data).digest("hex"),
    });
    pos = next + 2;
  }
  return parts;
}

// startMock serves a Roomcord API under /api/v1. responses overrides the reply
// for "members", "images" or "messages".
export async function startMock(responses: Record<string, MockResponse> = {}, delayMs = 0): Promise<MockRoomcord> {
  const requests: Recorded[] = [];
  const server = createServer(async (req, res) => {
    const raw = await readBody(req);
    const rec: Recorded = { method: req.method!, path: req.url!, headers: {} };
    if (req.headers.authorization) rec.headers.Authorization = req.headers.authorization;
    const ct = req.headers["content-type"];
    if (ct) rec.headers["Content-Type"] = ct;
    const mp = /^multipart\/form-data;\s*boundary=("?)([^";]+)\1/i.exec(ct ?? "");
    if (mp) {
      rec.headers["Content-Type"] = ct!.replace(mp[2], "<boundary>");
      rec.parts = parseMultipart(raw, mp[2]);
    } else if (raw.length) {
      rec.body = raw.toString("utf8");
    }
    requests.push(rec);
    if (delayMs) await new Promise((r) => setTimeout(r, delayMs));

    const url = new URL(req.url!, "http://mock");
    const parts = url.pathname.replace(/^\/api\/v1\//, "").split("/");
    let resp: MockResponse = { status: 404, body: `{"error":{"message":"no route"}}` };
    if (parts.length === 3 && parts[0] === "rooms") {
      const [, room, kind] = parts;
      const agent = roomAgents[room] ?? ["", ""];
      if (kind === "members" && req.method === "GET")
        resp = { status: 200, body: `{"data":[{"memberType":"user","userId":"u-1","displayName":"Ana Staff"},{"memberType":"agent","agentId":"${agent[0]}","displayName":"${agent[1]}"}]}` };
      else if (kind === "images" && req.method === "POST") resp = { status: 201, body: `{"data":{"url":"https://cdn.example.test/rooms/${room}/img-1.jpg"}}` };
      else if (kind === "messages" && req.method === "POST") resp = { status: 201, body: `{"data":{"id":"msg-1"}}` };
      if (responses[kind]) resp = responses[kind];
    }
    res.writeHead(resp.status, { "Content-Type": "application/json" });
    res.end(resp.body);
  });
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  const addr = server.address() as { port: number };
  return {
    url: `http://127.0.0.1:${addr.port}`,
    requests,
    server,
    close: () => new Promise<void>((r) => server.close(() => r())),
  };
}

// All config keys. Every test sets each one, so .dev.vars never leaks in.
const CONFIG_KEYS = [
  "ROOMCORD_API_URL", "ROOMCORD_BOT_TOKEN",
  "ROOM_VOLUNTEERS_ID", "ROOM_WORKSHOPS_ID", "ROOM_PROGRAMS_ID",
  "AGENT_VOLUNTEERS_ID", "AGENT_WORKSHOPS_ID", "AGENT_PROGRAMS_ID",
  "AGENT_VOLUNTEERS_NAME", "AGENT_WORKSHOPS_NAME", "AGENT_PROGRAMS_NAME",
  "RATE_LIMIT_MAX", "RATE_LIMIT_WINDOW_SEC", "PORTAL_DRY_RUN",
];

export function baseEnv(apiUrl: string): Record<string, string> {
  return {
    ROOMCORD_API_URL: apiUrl + "/api/v1/",
    ROOMCORD_BOT_TOKEN: fakeToken,
    ROOM_VOLUNTEERS_ID: roomVolunteers,
    ROOM_WORKSHOPS_ID: roomWorkshops,
    ROOM_PROGRAMS_ID: roomPrograms,
    AGENT_VOLUNTEERS_ID: agentVolunteer,
    AGENT_WORKSHOPS_ID: agentWorkshops,
    AGENT_PROGRAMS_ID: agentPrograms,
    RATE_LIMIT_MAX: "100",
    RATE_LIMIT_WINDOW_SEC: "600",
    PORTAL_DRY_RUN: "0",
  };
}

const configPath = fileURLToPath(new URL("../wrangler.jsonc", import.meta.url));

// startWorker runs the Worker with fresh storage. Keys missing from env are
// set to "" so the Worker uses its defaults, as the Go server does.
export async function startWorker(env: Record<string, string>): Promise<TestHarness> {
  const secrets: Record<string, string> = {};
  for (const k of CONFIG_KEYS) secrets[k] = env[k] ?? "";
  const harness = createTestHarness({ workers: [{ configPath, vars: secrets, secrets }] });
  await harness.listen();
  return harness;
}
