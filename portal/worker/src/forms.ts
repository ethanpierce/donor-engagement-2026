// Form validation and message format. Pure TypeScript, no Workers APIs, so
// the unit tests run it in Node. Ported from the Go server (forms.go).

export type Fields = Record<string, string>;
export type Errors = Record<string, string>;
export type Extra = { photo?: boolean; photoSkipped?: boolean };
export type Body = Record<string, unknown>;

export type Form = {
  title: string;
  validate(b: Body): { errors: Errors; fields: Fields };
  format(f: Fields, extra: Extra): string;
};

// ---------- text helpers ----------

// sliceUnits is s.slice(0, n) in UTF-16 units. A surrogate pair cut in half is
// dropped, like the Go server (Node kept the lone high surrogate).
export function sliceUnits(s: string, n: number): string {
  if (s.length <= n) return s;
  let out = s.slice(0, n);
  const last = out.charCodeAt(out.length - 1);
  if (last >= 0xd800 && last < 0xdc00) out = out.slice(0, -1);
  return out;
}

// One line, no control characters, no markup, no agent or user mentions.
export function clean(value: unknown, max = 200): string {
  if (value === undefined || value === null) return "";
  let s = String(value)
    .normalize("NFC")
    .replace(/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2060-\u206f]/g, " ")
    .replace(/[<>`*~|[\]]/g, "")
    .replace(/(^|[^\w.])@+/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
  if (s.length > max) s = sliceUnits(s, max - 1).trimEnd() + "…";
  return s;
}

// Date.parse for YYYY-MM-DD: month 01-12, day 01-31 (same rule as the Go server).
export function isDate(s: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const m = s.slice(5, 7);
  const d = s.slice(8, 10);
  return m >= "01" && m <= "12" && d >= "01" && d <= "31";
}
export const isEmail = (s: string) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(s);
export const isPhone = (s: string) => /^[+()\d\s.-]{7,20}$/.test(s) && s.replace(/\D/g, "").length >= 7;

const oneOf = (v: unknown, allowed: string[]) => (typeof v === "string" && allowed.includes(v) ? v : "");

// ---------- form definitions ----------

export const FORM_ORDER = ["volunteer", "workshop", "family", "approve"] as const;
export type FormId = (typeof FORM_ORDER)[number];

export const FORMS: Record<FormId, Form> = {
  volunteer: {
    title: "Volunteer check-in",
    validate(b) {
      const f: Fields = {
        name: clean(b.name, 80),
        phone: clean(b.phone, 20),
        date: clean(b.date, 10),
        hours: clean(b.hours, 5),
        met: clean(b.met, 40),
        happened: clean(b.happened, 600),
        urgent: b.urgent === "yes" ? "yes" : "no",
        urgentText: clean(b.urgentText, 300),
      };
      const e: Errors = {};
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
      const f: Fields = {
        school: clean(b.school, 120),
        contact: clean(b.contact, 80),
        email: clean(b.email, 120),
        phone: clean(b.phone, 20),
        dates: clean(b.dates, 160),
        grade: clean(b.grade, 30),
        headcount: clean(b.headcount, 4),
        topic: oneOf(b.topic, ["safety", "mental-health", "other"]),
        topicOther: clean(b.topicOther, 120),
        language: clean(b.language, 30),
        mode: oneOf(b.mode, ["in-person", "online"]),
        notes: clean(b.notes, 600),
      };
      const e: Errors = {};
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
      const f: Fields = {
        parent: clean(b.parent, 80),
        phone: clean(b.phone, 20),
        email: clean(b.email, 120),
        language: clean(b.language, 30),
        child: clean(b.child, 60),
        age: clean(b.age, 3),
        school: clean(b.school, 120),
        program: oneOf(b.program, ["mentoring", "family-counseling", "workshops"]),
      };
      const consent = b.consent === true || b.consent === "yes" || b.consent === "on";
      const e: Errors = {};
      for (const k of ["parent", "language", "child", "school"]) if (!f[k]) e[k] = "required";
      if (!f.phone && !f.email) e.phone = "contact";
      if (f.phone && !isPhone(f.phone)) e.phone = "phone";
      if (f.email && !isEmail(f.email)) e.email = "email";
      const a = Number(f.age);
      if (!f.age) e.age = "required";
      else if (!(Number.isInteger(a) && a >= 3 && a <= 21)) e.age = "age";
      if (!f.program) e.program = "required";
      if (!consent) e.consent = "consent";
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
      const f: Fields = {
        request: clean(b.request, 12).toUpperCase(),
        version: clean(b.version, 6).toLowerCase(),
        decision: oneOf(b.decision, ["approve", "changes"]),
        name: clean(b.name, 80),
        comment: clean(b.comment, 600),
      };
      const e: Errors = {};
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

// decodeBase64Lenient decodes like Node's Buffer.from(s, "base64"): it stops at
// the first "=" and drops a final partial group of one character. The input
// holds only base64 alphabet characters and "=".
export function decodeBase64Lenient(s: string): Uint8Array {
  const eq = s.indexOf("=");
  if (eq >= 0) s = s.slice(0, eq);
  if (s.length % 4 === 1) s = s.slice(0, -1);
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  const out = new Uint8Array(Math.floor((s.length * 3) / 4));
  let acc = 0;
  let bits = 0;
  let n = 0;
  for (let i = 0; i < s.length; i++) {
    acc = ((acc << 6) | alphabet.indexOf(s[i])) & 0xffffff;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      out[n++] = (acc >> bits) & 0xff;
    }
  }
  return out.subarray(0, n);
}
