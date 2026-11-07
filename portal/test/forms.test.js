import { test } from "node:test";
import assert from "node:assert/strict";
import { FORMS, clean } from "../server.js";

test("clean strips mentions, markup and control characters, keeps emails", () => {
  assert.equal(clean("hi @Tidepath Director <b>x</b>\n\tok"), "hi Tidepath Director bx/b ok");
  assert.equal(clean("ana_lee@school.org"), "ana_lee@school.org");
  assert.equal(clean("a".repeat(50), 10).length, 10);
});

test("volunteer check-in formats one compact line", () => {
  const { errors, fields } = FORMS.volunteer.validate({
    name: "Maria Alvarez", date: "2026-11-07", hours: "1", met: "Kevin",
    happened: "Homework help", urgent: "yes", urgentText: "needs a laptop for school",
  });
  assert.deepEqual(errors, {});
  const first = FORMS.volunteer.format(fields, {}).split("\n")[0];
  assert.equal(first, "Portal · Volunteer check-in · Maria Alvarez · 2026-11-07 · 1h · met Kevin · urgent: needs a laptop for school");
});

test("volunteer check-in rejects bad input", () => {
  const { errors } = FORMS.volunteer.validate({ hours: "30", urgent: "yes", phone: "abc" });
  assert.deepEqual(errors, { name: "required", phone: "phone", date: "date", hours: "hours", happened: "required", urgentText: "required" });
});

test("workshop request needs email, topic and mode", () => {
  const { errors } = FORMS.workshop.validate({ school: "X", contact: "Y", dates: "d", grade: "7", language: "English", email: "bad", headcount: "2.5", topic: "other" });
  assert.deepEqual(errors, { email: "email", headcount: "number", topicOther: "required", mode: "required" });
});

test("family sign-up needs a contact and consent", () => {
  const { errors } = FORMS.family.validate({ parent: "P", language: "Spanish", child: "C", school: "S", age: "9", program: "mentoring" });
  assert.deepEqual(errors, { phone: "contact", consent: "consent" });
});

test("approval message has the exact approval phrase", () => {
  const ok = FORMS.approve.validate({ request: "w004", version: "V2", decision: "approve" });
  assert.deepEqual(ok.errors, {});
  assert.match(FORMS.approve.format(ok.fields), /^School approved W004 v2/);
  const ch = FORMS.approve.validate({ request: "W004", version: "v2", decision: "changes" });
  assert.deepEqual(ch.errors, { comment: "required" });
  assert.deepEqual(FORMS.approve.validate({ request: "X1", version: "2", decision: "approve" }).errors, { request: "request", version: "version" });
});
