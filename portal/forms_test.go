package main

// Ported from the Node test suite (test/forms.test.js), plus helper cases.

import (
	"encoding/json"
	"math"
	"regexp"
	"strings"
	"testing"
)

func errsJSON(e ordered) string { return string(marshalJS(e)) }

func TestCleanStripsMentionsMarkupControlKeepsEmails(t *testing.T) {
	if got := clean("hi @Tidepath Director <b>x</b>\n\tok", 200); got != "hi Tidepath Director bx/b ok" {
		t.Fatalf("got %q", got)
	}
	if got := clean("ana_lee@school.org", 200); got != "ana_lee@school.org" {
		t.Fatalf("got %q", got)
	}
	if got := clean(strings.Repeat("a", 50), 10); utf16Len(got) != 10 {
		t.Fatalf("len %d", utf16Len(got))
	}
}

func TestVolunteerFormatsOneCompactLine(t *testing.T) {
	errs, f := forms["volunteer"].validate(map[string]any{
		"name": "Maria Alvarez", "date": "2026-11-07", "hours": "1", "met": "Kevin",
		"happened": "Homework help", "urgent": "yes", "urgentText": "needs a laptop for school",
	})
	if len(errs) != 0 {
		t.Fatalf("errors %s", errsJSON(errs))
	}
	first := strings.Split(forms["volunteer"].format(f, extra{}), "\n")[0]
	if want := "Portal · Volunteer check-in · Maria Alvarez · 2026-11-07 · 1h · met Kevin · urgent: needs a laptop for school"; first != want {
		t.Fatalf("got %q", first)
	}
}

func TestVolunteerRejectsBadInput(t *testing.T) {
	errs, _ := forms["volunteer"].validate(map[string]any{"hours": "30", "urgent": "yes", "phone": "abc"})
	if got, want := errsJSON(errs), `{"name":"required","phone":"phone","date":"date","hours":"hours","happened":"required","urgentText":"required"}`; got != want {
		t.Fatalf("got %s", got)
	}
}

func TestWorkshopNeedsEmailTopicMode(t *testing.T) {
	errs, _ := forms["workshop"].validate(map[string]any{"school": "X", "contact": "Y", "dates": "d", "grade": "7", "language": "English", "email": "bad", "headcount": "2.5", "topic": "other"})
	if got, want := errsJSON(errs), `{"email":"email","headcount":"number","topicOther":"required","mode":"required"}`; got != want {
		t.Fatalf("got %s", got)
	}
}

func TestFamilyNeedsContactAndConsent(t *testing.T) {
	errs, _ := forms["family"].validate(map[string]any{"parent": "P", "language": "Spanish", "child": "C", "school": "S", "age": "9", "program": "mentoring"})
	if got, want := errsJSON(errs), `{"phone":"contact","consent":"consent"}`; got != want {
		t.Fatalf("got %s", got)
	}
}

func TestApprovalHasExactPhrase(t *testing.T) {
	errs, f := forms["approve"].validate(map[string]any{"request": "w004", "version": "V2", "decision": "approve"})
	if len(errs) != 0 {
		t.Fatalf("errors %s", errsJSON(errs))
	}
	if !regexp.MustCompile(`^School approved W004 v2`).MatchString(forms["approve"].format(f, extra{})) {
		t.Fatal("bad approval text")
	}
	errs, _ = forms["approve"].validate(map[string]any{"request": "W004", "version": "v2", "decision": "changes"})
	if got := errsJSON(errs); got != `{"comment":"required"}` {
		t.Fatalf("got %s", got)
	}
	errs, _ = forms["approve"].validate(map[string]any{"request": "X1", "version": "2", "decision": "approve"})
	if got := errsJSON(errs); got != `{"request":"request","version":"version"}` {
		t.Fatalf("got %s", got)
	}
}

// Values below were checked against Node 24.
func TestJSHelpers(t *testing.T) {
	nums := map[string]float64{"0x1F": 31, " 12 ": 12, "1e3": 1000, ".5": 0.5, "5.": 5, "": 0, "0b11": 3, "0o7": 7, "Infinity": math.Inf(1)}
	for in, want := range nums {
		if got := jsNumber(in); got != want {
			t.Errorf("Number(%q) = %v, want %v", in, got, want)
		}
	}
	for _, in := range []string{"+0x10", "1_0", "abc", "1.2.3"} {
		if !math.IsNaN(jsNumber(in)) {
			t.Errorf("Number(%q) should be NaN", in)
		}
	}
	strs := map[float64]string{1e21: "1e+21", 1.5e-7: "1.5e-7", 0.000001: "0.000001", 123456789012345680000: "123456789012345680000", 1.25: "1.25"}
	for in, want := range strs {
		if got := jsNumberString(in); got != want {
			t.Errorf("String(%v) = %q, want %q", in, got, want)
		}
	}
	var arr any
	json.Unmarshal([]byte(`[1,null,"a",{"x":1},true]`), &arr)
	if got := jsString(arr); got != "1,,a,[object Object],true" {
		t.Errorf("String(array) = %q", got)
	}
	b64 := map[string]string{"QUJD": "ABC", "QUI": "AB", "QQ": "A", "Q": "", "QUJD=QUJD": "ABC", "QU=JD": "A", "QUJDQ": "ABC", "QUJDRA==": "ABCD", "QUJ=D": "AB"}
	for in, want := range b64 {
		if got := string(decodeBase64Lenient(in)); got != want {
			t.Errorf("base64 %q = %q, want %q", in, got, want)
		}
	}
	dates := map[string]bool{"2026-02-30": true, "2026-02-31": true, "2026-02-32": false, "2026-13-01": false, "2026-00-10": false, "0000-01-01": true, "2026-01-00": false, "2026-1-01": false}
	for in, want := range dates {
		if isDate(in) != want {
			t.Errorf("isDate(%q) != %v", in, want)
		}
	}
	emails := map[string]bool{"a@b.co": true, "a@b.c": false, "a@.co": false, "a@b..co": true, "a b@c.de": false, "a@b@c.de": false, "a@b.c😀": true}
	for in, want := range emails {
		if isEmail(in) != want {
			t.Errorf("isEmail(%q) != %v", in, want)
		}
	}
	if got := encodeURIComponent("a b/c?d=é!~*'()"); got != "a%20b%2Fc%3Fd%3D%C3%A9!~*'()" {
		t.Errorf("encodeURIComponent = %q", got)
	}
}
