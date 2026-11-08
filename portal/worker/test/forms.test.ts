// Validation and message format. Ported from the Node test suite
// (test/forms.test.js) and the Go forms_test.go helper cases.
import { describe, expect, test } from "vitest";
import { FORMS, clean, decodeBase64Lenient, isDate, isEmail } from "../src/forms";

describe("forms", () => {
  test("clean strips mentions, markup and control characters, keeps emails", () => {
    expect(clean("hi @Tidepath Director <b>x</b>\n\tok")).toBe("hi Tidepath Director bx/b ok");
    expect(clean("ana_lee@school.org")).toBe("ana_lee@school.org");
    expect(clean("a".repeat(50), 10).length).toBe(10);
  });

  test("clean drops a surrogate pair cut by the length limit (Go behaviour)", () => {
    expect(clean("ab😀cd", 4)).toBe("ab…");
    expect(clean("ab😀cd", 5)).toBe("ab😀…");
  });

  test("volunteer check-in formats one compact line", () => {
    const { errors, fields } = FORMS.volunteer.validate({
      name: "Maria Alvarez", date: "2026-11-07", hours: "1", met: "Kevin",
      happened: "Homework help", urgent: "yes", urgentText: "needs a laptop for school",
    });
    expect(errors).toEqual({});
    const first = FORMS.volunteer.format(fields, {}).split("\n")[0];
    expect(first).toBe("Portal · Volunteer check-in · Maria Alvarez · 2026-11-07 · 1h · met Kevin · urgent: needs a laptop for school");
  });

  test("volunteer check-in rejects bad input", () => {
    const { errors } = FORMS.volunteer.validate({ hours: "30", urgent: "yes", phone: "abc" });
    expect(JSON.stringify(errors)).toBe(JSON.stringify({ name: "required", phone: "phone", date: "date", hours: "hours", happened: "required", urgentText: "required" }));
  });

  test("workshop request needs email, topic and mode", () => {
    const { errors } = FORMS.workshop.validate({ school: "X", contact: "Y", dates: "d", grade: "7", language: "English", email: "bad", headcount: "2.5", topic: "other" });
    expect(JSON.stringify(errors)).toBe(JSON.stringify({ email: "email", headcount: "number", topicOther: "required", mode: "required" }));
  });

  test("family sign-up needs a contact and consent", () => {
    const { errors } = FORMS.family.validate({ parent: "P", language: "Spanish", child: "C", school: "S", age: "9", program: "mentoring" });
    expect(JSON.stringify(errors)).toBe(JSON.stringify({ phone: "contact", consent: "consent" }));
  });

  test("approval message has the exact approval phrase", () => {
    const ok = FORMS.approve.validate({ request: "w004", version: "V2", decision: "approve" });
    expect(ok.errors).toEqual({});
    expect(FORMS.approve.format(ok.fields, {})).toMatch(/^School approved W004 v2/);
    expect(FORMS.approve.validate({ request: "W004", version: "v2", decision: "changes" }).errors).toEqual({ comment: "required" });
    expect(FORMS.approve.validate({ request: "X1", version: "2", decision: "approve" }).errors).toEqual({ request: "request", version: "version" });
  });

  test("helpers match the Go server", () => {
    const b64: Record<string, string> = { QUJD: "ABC", QUI: "AB", QQ: "A", Q: "", "QUJD=QUJD": "ABC", "QU=JD": "A", QUJDQ: "ABC", "QUJDRA==": "ABCD", "QUJ=D": "AB" };
    for (const [i, w] of Object.entries(b64)) expect(new TextDecoder().decode(decodeBase64Lenient(i)), i).toBe(w);
    const dates: Record<string, boolean> = { "2026-02-30": true, "2026-02-31": true, "2026-02-32": false, "2026-13-01": false, "2026-00-10": false, "0000-01-01": true, "2026-01-00": false, "2026-1-01": false };
    for (const [i, w] of Object.entries(dates)) expect(isDate(i), i).toBe(w);
    const emails: Record<string, boolean> = { "a@b.co": true, "a@b.c": false, "a@.co": false, "a@b..co": true, "a b@c.de": false, "a@b@c.de": false, "a@b.c😀": true };
    for (const [i, w] of Object.entries(emails)) expect(isEmail(i), i).toBe(w);
  });
});
