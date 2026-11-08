// Worker behaviour that the golden files do not show.
import { afterEach, expect, test } from "vitest";
import type { TestHarness } from "wrangler";
import { baseEnv, fakeToken, startMock, startWorker, type MockRoomcord } from "./helpers";

const approve = JSON.stringify({ request: "W004", version: "v2", decision: "approve" });
let harness: TestHarness | undefined;
let mock: MockRoomcord | undefined;
afterEach(async () => {
  await harness?.close();
  await mock?.close();
  harness = mock = undefined;
});

async function start(over: Record<string, string> = {}) {
  mock = await startMock();
  harness = await startWorker({ ...baseEnv(mock.url), ...over });
  return harness;
}

const submit = (h: TestHarness, body: string, ip?: string) =>
  h.fetch("/api/submit/approve", { method: "POST", headers: { "Content-Type": "application/json", ...(ip ? { "CF-Connecting-IP": ip } : {}) }, body });

test("agent name is cached per isolate", async () => {
  const h = await start();
  for (let i = 0; i < 3; i++) expect((await submit(h, approve)).status).toBe(200);
  expect(mock!.requests.filter((r) => r.path.includes("/members")).length).toBe(1);
});

test("RATE_LIMIT_MAX=0 means no limit", async () => {
  const h = await start({ RATE_LIMIT_MAX: "0" });
  for (let i = 0; i < 3; i++) expect((await submit(h, approve)).status).toBe(200);
});

test("rate limit is per CF-Connecting-IP and ignores X-Forwarded-For", async () => {
  const h = await start({ RATE_LIMIT_MAX: "1", RATE_LIMIT_WINDOW_SEC: "60" });
  expect((await submit(h, approve, "198.51.100.1")).status).toBe(200);
  const r = await submit(h, approve, "198.51.100.1");
  expect(r.status).toBe(429);
  expect(r.headers.get("Retry-After")).toBe("60");
  expect(await r.json()).toEqual({ ok: false, error: "rate_limited", retryAfter: 60 });
  expect((await submit(h, approve, "198.51.100.2")).status).toBe(200);
  const spoof = await h.fetch("/api/submit/approve", { method: "POST", headers: { "Content-Type": "application/json", "CF-Connecting-IP": "198.51.100.2", "X-Forwarded-For": "203.0.113.9" }, body: approve });
  expect(spoof.status).toBe(429);
});

test("logs are JSON lines without the token, content only in dry run", async () => {
  const h = await start({ PORTAL_DRY_RUN: "1" });
  expect((await submit(h, approve)).status).toBe(200);
  const lines = h.getLogs().map((l) => l.message);
  const dry = lines.map((l) => { try { return JSON.parse(l); } catch { return null; } }).find((l) => l?.msg === "dry run, not posted");
  expect(dry).toMatchObject({ level: "info", form: "approve", content: "@Workshops Agent School approved W004 v2. Sent from the Portal." });
  expect(lines.join("\n")).not.toContain(fakeToken);
});
