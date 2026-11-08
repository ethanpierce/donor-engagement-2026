// Replays every golden case in ../testdata/parity/ (captured from the Node
// server, also used by the Go parity_test.go) against the Worker, with a mock
// Roomcord API, and compares the answers and the outgoing Roomcord calls.
//
// Same rules as the Go harness: the multipart boundary shows as <boundary>, the
// reference code as TP-<ref>, and a surrogate pair cut by a length limit is
// dropped (knownDifferences). Worker-specific: there is no TRUST_PROXY. The
// client IP is CF-Connecting-IP, so the trust-proxy case sends the first
// X-Forwarded-For entry as CF-Connecting-IP. X-Forwarded-For is ignored.
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import { afterEach, describe, expect, test } from "vitest";
import type { TestHarness } from "wrangler";
import { baseEnv, startMock, startWorker, type MockResponse, type MockRoomcord, type Recorded } from "./helpers";

const portal = fileURLToPath(new URL("../..", import.meta.url));
const dir = join(portal, "testdata/parity");
const publicDir = join(portal, "public");

type Step = { method: string; path: string; headers?: Record<string, string>; body?: string; expect: Expected };
type Expected = { status: number; headers: Record<string, string>; body?: string; bodyFile?: string };
type Case = { name: string; env?: Record<string, string>; mockResponses?: Record<string, MockResponse>; steps: Step[]; roomcord: Recorded[] };

const RECORDED_HEADERS = ["Content-Type", "Cache-Control", "Allow", "Retry-After", "X-Content-Type-Options", "Referrer-Policy", "X-Frame-Options", "Content-Security-Policy"];

const knownDifferences: Partial<Record<string, (s: string) => string>> = {
  sanitize: (s) => s.replaceAll("\\ud83d…", "…"),
};

function requestHeaders(c: Case, s: Step): Record<string, string> {
  const h: Record<string, string> = {};
  for (const [k, v] of Object.entries(s.headers ?? {})) {
    if (k.toLowerCase() === "x-forwarded-for" && c.env?.TRUST_PROXY === "1") h["CF-Connecting-IP"] = v.split(",")[0].trim();
    else h[k] = v;
  }
  return h;
}

const cases = readdirSync(dir).filter((f) => f.endsWith(".json")).sort();

let harness: TestHarness | undefined;
let mock: MockRoomcord | undefined;
afterEach(async () => {
  await harness?.close();
  await mock?.close();
  harness = mock = undefined;
});

describe("parity with the Go server golden files", () => {
  test("there are golden cases", () => expect(cases.length).toBeGreaterThanOrEqual(19));

  for (const file of cases) {
    const c: Case = JSON.parse(readFileSync(join(dir, file), "utf8"));
    test(c.name, async () => {
      mock = await startMock(c.mockResponses ?? {});
      harness = await startWorker({ ...baseEnv(mock.url), ...(c.env ?? {}) });
      for (const [i, s] of c.steps.entries()) {
        const res = await harness.fetch(s.path, { method: s.method, headers: requestHeaders(c, s), body: s.body || undefined, redirect: "manual" });
        const text = await res.text();
        const headers: Record<string, string> = {};
        for (const h of RECORDED_HEADERS) {
          const v = res.headers.get(h);
          if (v) headers[h] = v;
        }
        let body = text;
        if ((res.headers.get("content-type") ?? "").startsWith("application/json")) body = body.replace(/TP-[0-9A-F]{6}/g, "TP-<ref>");
        let want = s.expect.body ?? "";
        if (s.expect.bodyFile) want = readFileSync(join(publicDir, s.expect.bodyFile), "utf8");
        if (s.method === "HEAD") body = want = "";
        expect({ step: i, status: res.status, headers, body }, `step ${i} ${s.method} ${s.path}`).toEqual({ step: i, status: s.expect.status, headers: s.expect.headers, body: want });
      }
      const fix = knownDifferences[c.name];
      const golden = c.roomcord.map((r) => (fix && r.body ? { ...r, body: fix(r.body) } : r));
      expect(mock.requests).toEqual(golden);
    });
  }
});
