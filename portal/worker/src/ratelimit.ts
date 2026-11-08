import { DurableObject } from "cloudflare:workers";

// One object per client IP (idFromName(ip)). It keeps the post times (ms) of
// the sliding window in SQLite, so it runs on the Free plan.
export class RateLimiter extends DurableObject<object> {
  constructor(ctx: DurableObjectState, env: object) {
    super(ctx, env);
    ctx.storage.sql.exec("CREATE TABLE IF NOT EXISTS hits (t INTEGER NOT NULL)");
  }

  // hit records a post and returns 0, or the seconds to wait when the IP is
  // over the limit. Same semantics as the Go and Node servers.
  hit(windowMs: number, max: number): number {
    const sql = this.ctx.storage.sql;
    const now = Date.now();
    const rows = sql.exec<{ id: number; t: number }>("SELECT rowid AS id, t FROM hits ORDER BY rowid").toArray();
    const list: number[] = [];
    for (const r of rows) {
      if (now - r.t < windowMs) list.push(r.t);
      else sql.exec("DELETE FROM hits WHERE rowid = ?", r.id);
    }
    if (list.length >= max) {
      if (list.length === 0) return 0; // RATE_LIMIT_MAX=0: never limits
      const wait = Math.ceil((windowMs - (now - list[0])) / 1000);
      return wait > 0 ? wait : 0;
    }
    sql.exec("INSERT INTO hits (t) VALUES (?)", now);
    return 0;
  }
}
