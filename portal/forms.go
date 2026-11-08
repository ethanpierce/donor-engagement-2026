package main

import (
	"math"
	"regexp"
	"strings"

	"golang.org/x/text/unicode/norm"
)

// ---------- text helpers ----------

var (
	reControl = regexp.MustCompile(`[\x{0000}-\x{001f}\x{007f}-\x{009f}\x{200b}-\x{200f}\x{2028}-\x{202e}\x{2060}-\x{206f}]`)
	reMarkup  = regexp.MustCompile("[<>`*~|\\[\\]]")
	reMention = regexp.MustCompile(`(^|[^\w.])@+`)
	reSpaces  = regexp.MustCompile(`[` + jsSpaceClass + `]+`)
	reDate    = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}$`)
	rePhone   = regexp.MustCompile(`^[+()0-9` + jsSpaceClass + `.\-]{7,20}$`)
	reNonDig  = regexp.MustCompile(`[^0-9]`)
	reRequest = regexp.MustCompile(`^W\d{3,6}$`)
	reVersion = regexp.MustCompile(`^v\d{1,3}$`)
)

// clean makes one line: no control characters, no markup, no agent or user
// mentions, at most max UTF-16 units (ending in "…" when cut).
func clean(v any, max int) string {
	if v == nil {
		return ""
	}
	s := norm.NFC.String(jsString(v))
	s = reControl.ReplaceAllString(s, " ")
	s = reMarkup.ReplaceAllString(s, "")
	s = reMention.ReplaceAllString(s, "${1}")
	s = reSpaces.ReplaceAllString(s, " ")
	s = jsTrim(s)
	if utf16Len(s) > max {
		s = strings.TrimRightFunc(utf16Prefix(s, max-1), isJSSpace) + "…"
	}
	return s
}

// isDate matches Date.parse for YYYY-MM-DD: month 01-12, day 01-31.
func isDate(s string) bool {
	if !reDate.MatchString(s) {
		return false
	}
	m, d := s[5:7], s[8:10]
	return m >= "01" && m <= "12" && d >= "01" && d <= "31"
}

// isEmail is /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.
func isEmail(s string) bool {
	if strings.IndexFunc(s, isJSSpace) >= 0 || strings.Count(s, "@") != 1 {
		return false
	}
	local, domain, _ := strings.Cut(s, "@")
	if local == "" || len(domain) < 2 {
		return false
	}
	i := strings.IndexByte(domain[1:], '.')
	return i >= 0 && utf16Len(domain[i+2:]) >= 2
}

func isPhone(s string) bool {
	return rePhone.MatchString(s) && len(reNonDig.ReplaceAllString(s, "")) >= 7
}

func strIs(v any, want string) bool {
	s, ok := v.(string)
	return ok && s == want
}

func oneOf(v any, allowed ...string) string {
	for _, a := range allowed {
		if strIs(v, a) {
			return a
		}
	}
	return ""
}

// ---------- form definitions ----------

type extra struct{ photo, photoSkipped bool }

type form struct {
	title    string
	validate func(b map[string]any) (errs ordered, f map[string]string)
	format   func(f map[string]string, x extra) string
}

var formOrder = []string{"volunteer", "workshop", "family", "approve"}

var forms = map[string]form{
	"volunteer": {
		title: "Volunteer check-in",
		validate: func(b map[string]any) (ordered, map[string]string) {
			f := map[string]string{
				"name":       clean(b["name"], 80),
				"phone":      clean(b["phone"], 20),
				"date":       clean(b["date"], 10),
				"hours":      clean(b["hours"], 5),
				"met":        clean(b["met"], 40),
				"happened":   clean(b["happened"], 600),
				"urgent":     "no",
				"urgentText": clean(b["urgentText"], 300),
			}
			if strIs(b["urgent"], "yes") {
				f["urgent"] = "yes"
			}
			var e ordered
			if f["name"] == "" {
				e.set("name", "required")
			}
			if f["phone"] != "" && !isPhone(f["phone"]) {
				e.set("phone", "phone")
			}
			if !isDate(f["date"]) {
				e.set("date", "date")
			}
			h := jsNumber(f["hours"])
			if f["hours"] == "" {
				e.set("hours", "required")
			} else if !(h > 0 && h <= 24) {
				e.set("hours", "hours")
			} else {
				f["hours"] = jsNumberString(math.Floor(h*4+0.5) / 4)
			}
			if f["happened"] == "" {
				e.set("happened", "required")
			}
			if f["urgent"] == "yes" && f["urgentText"] == "" {
				e.set("urgentText", "required")
			}
			return e, f
		},
		format: func(f map[string]string, x extra) string {
			head := []string{"Portal", "Volunteer check-in", f["name"], f["date"], f["hours"] + "h"}
			if f["met"] != "" {
				head = append(head, "met "+f["met"])
			}
			if f["urgent"] == "yes" {
				head = append(head, "urgent: "+f["urgentText"])
			} else {
				head = append(head, "urgent: no")
			}
			lines := []string{strings.Join(head, " · "), "What happened: " + f["happened"]}
			if f["phone"] != "" {
				lines = append(lines, "Volunteer phone: "+f["phone"])
			}
			if x.photo {
				lines = append(lines, "Photo attached.")
			} else if x.photoSkipped {
				lines = append(lines, "Photo: upload failed, not attached.")
			}
			return strings.Join(lines, "\n")
		},
	},

	"workshop": {
		title: "Workshop request",
		validate: func(b map[string]any) (ordered, map[string]string) {
			f := map[string]string{
				"school":     clean(b["school"], 120),
				"contact":    clean(b["contact"], 80),
				"email":      clean(b["email"], 120),
				"phone":      clean(b["phone"], 20),
				"dates":      clean(b["dates"], 160),
				"grade":      clean(b["grade"], 30),
				"headcount":  clean(b["headcount"], 4),
				"topic":      oneOf(b["topic"], "safety", "mental-health", "other"),
				"topicOther": clean(b["topicOther"], 120),
				"language":   clean(b["language"], 30),
				"mode":       oneOf(b["mode"], "in-person", "online"),
				"notes":      clean(b["notes"], 600),
			}
			var e ordered
			for _, k := range []string{"school", "contact", "dates", "grade", "language"} {
				if f[k] == "" {
					e.set(k, "required")
				}
			}
			if !isEmail(f["email"]) {
				if f["email"] != "" {
					e.set("email", "email")
				} else {
					e.set("email", "required")
				}
			}
			if f["phone"] != "" && !isPhone(f["phone"]) {
				e.set("phone", "phone")
			}
			n := jsNumber(f["headcount"])
			if f["headcount"] == "" {
				e.set("headcount", "required")
			} else if !(jsIsInteger(n) && n > 0 && n <= 2000) {
				e.set("headcount", "number")
			}
			if f["topic"] == "" {
				e.set("topic", "required")
			}
			if f["topic"] == "other" && f["topicOther"] == "" {
				e.set("topicOther", "required")
			}
			if f["mode"] == "" {
				e.set("mode", "required")
			}
			return e, f
		},
		format: func(f map[string]string, _ extra) string {
			topic := strings.Replace(f["topic"], "-", " ", 1)
			if f["topic"] == "other" {
				topic = "other: " + f["topicOther"]
			}
			head := []string{"Portal", "Workshop request", f["school"], "grade " + f["grade"], f["headcount"] + " students", topic, strings.Replace(f["mode"], "-", " ", 1), f["language"]}
			contact := "Contact: " + f["contact"] + " · " + f["email"]
			if f["phone"] != "" {
				contact += " · " + f["phone"]
			}
			lines := []string{strings.Join(head, " · "), "Preferred dates: " + f["dates"], contact}
			if f["notes"] != "" {
				lines = append(lines, "Notes: "+f["notes"])
			}
			return strings.Join(lines, "\n")
		},
	},

	"family": {
		title: "Family sign-up",
		validate: func(b map[string]any) (ordered, map[string]string) {
			f := map[string]string{
				"parent":   clean(b["parent"], 80),
				"phone":    clean(b["phone"], 20),
				"email":    clean(b["email"], 120),
				"language": clean(b["language"], 30),
				"child":    clean(b["child"], 60),
				"age":      clean(b["age"], 3),
				"school":   clean(b["school"], 120),
				"program":  oneOf(b["program"], "mentoring", "family-counseling", "workshops"),
			}
			consent := b["consent"] == true || strIs(b["consent"], "yes") || strIs(b["consent"], "on")
			var e ordered
			for _, k := range []string{"parent", "language", "child", "school"} {
				if f[k] == "" {
					e.set(k, "required")
				}
			}
			if f["phone"] == "" && f["email"] == "" {
				e.set("phone", "contact")
			}
			if f["phone"] != "" && !isPhone(f["phone"]) {
				e.set("phone", "phone")
			}
			if f["email"] != "" && !isEmail(f["email"]) {
				e.set("email", "email")
			}
			a := jsNumber(f["age"])
			if f["age"] == "" {
				e.set("age", "required")
			} else if !(jsIsInteger(a) && a >= 3 && a <= 21) {
				e.set("age", "age")
			}
			if f["program"] == "" {
				e.set("program", "required")
			}
			if !consent {
				e.set("consent", "consent")
			}
			return e, f
		},
		format: func(f map[string]string, _ extra) string {
			head := []string{"Portal", "Family sign-up", f["parent"], "child " + f["child"] + " (" + f["age"] + ")", f["school"], strings.Replace(f["program"], "-", " ", 1), "language " + f["language"]}
			var contact []string
			for _, c := range []string{f["phone"], f["email"]} {
				if c != "" {
					contact = append(contact, c)
				}
			}
			return strings.Join([]string{strings.Join(head, " · "), "Contact: " + strings.Join(contact, " · "), "Consent to contact: yes"}, "\n")
		},
	},

	"approve": {
		title: "Slide approval",
		validate: func(b map[string]any) (ordered, map[string]string) {
			f := map[string]string{
				"request":  strings.ToUpper(clean(b["request"], 12)),
				"version":  strings.ToLower(clean(b["version"], 6)),
				"decision": oneOf(b["decision"], "approve", "changes"),
				"name":     clean(b["name"], 80),
				"comment":  clean(b["comment"], 600),
			}
			var e ordered
			if !reRequest.MatchString(f["request"]) {
				e.set("request", "request")
			}
			if !reVersion.MatchString(f["version"]) {
				e.set("version", "version")
			}
			if f["decision"] == "" {
				e.set("decision", "required")
			}
			if f["decision"] == "changes" && f["comment"] == "" {
				e.set("comment", "required")
			}
			return e, f
		},
		format: func(f map[string]string, _ extra) string {
			by := ""
			if f["name"] != "" {
				by = " (by " + f["name"] + ")"
			}
			if f["decision"] == "approve" {
				return "School approved " + f["request"] + " " + f["version"] + by + ". Sent from the Portal."
			}
			return "School requested changes to " + f["request"] + " " + f["version"] + by + ". Sent from the Portal.\nChanges: " + f["comment"]
		},
	},
}
