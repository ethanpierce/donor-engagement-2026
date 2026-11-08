package main

// Parity with the retired Node server (server.js).
//
// Each case sends requests to the portal while the portal talks to a mock
// Roomcord API. The golden files in testdata/parity/ hold what the Node server
// answered and what it sent to Roomcord. They were captured with
//
//	PARITY_CAPTURE_NODE=/path/to/server.js go test -run TestCaptureNodeGolden
//
// TestParity replays every case against the Go server and compares.
// Ignored as random: the multipart boundary (shown as <boundary>) and the
// reference code value (shown as TP-<ref>, its format is checked).
// Known difference: when a length cut splits a surrogate pair (an emoji),
// Node sent the lone high surrogate ("\ud83d…"). Go drops the half emoji
// ("…"). knownDifferences applies exactly that change to the golden data.
// Not recorded: transport headers that each HTTP client sets differently
// (User-Agent, Accept, Accept-Encoding, Accept-Language, Sec-Fetch-Mode,
// Connection, Content-Length, Date, Keep-Alive).

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"io/fs"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"regexp"
	"sort"
	"strings"
	"testing"
	"time"
)

type step struct {
	Method  string            `json:"method"`
	Path    string            `json:"path"`
	Headers map[string]string `json:"headers,omitempty"`
	Body    string            `json:"body,omitempty"`
	Expect  *response         `json:"expect,omitempty"`
}

type response struct {
	Status   int               `json:"status"`
	Headers  map[string]string `json:"headers"`
	Body     string            `json:"body,omitempty"`
	BodyFile string            `json:"bodyFile,omitempty"` // body equals public/<file>
}

type parityCase struct {
	Name      string                  `json:"name"`
	Env       map[string]string       `json:"env,omitempty"` // overrides of baseEnv
	Responses map[string]mockResponse `json:"mockResponses,omitempty"`
	Steps     []step                  `json:"steps"`
	Roomcord  []recorded              `json:"roomcord"` // requests the server sent, in order
}

var recordedResponseHeaders = []string{"Content-Type", "Cache-Control", "Allow", "Retry-After", "X-Content-Type-Options", "Referrer-Policy", "X-Frame-Options", "Content-Security-Policy"}

func baseEnv(apiURL string) map[string]string {
	return map[string]string{
		"ROOMCORD_API_URL":      apiURL + "/api/v1/",
		"ROOMCORD_BOT_TOKEN":    fakeToken,
		"ROOM_VOLUNTEERS_ID":    roomVolunteers,
		"ROOM_WORKSHOPS_ID":     roomWorkshops,
		"ROOM_PROGRAMS_ID":      roomPrograms,
		"AGENT_VOLUNTEERS_ID":   agentVolunteer,
		"AGENT_WORKSHOPS_ID":    agentWorkshops,
		"AGENT_PROGRAMS_ID":     agentPrograms,
		"RATE_LIMIT_MAX":        "100",
		"RATE_LIMIT_WINDOW_SEC": "600",
		"TRUST_PROXY":           "0",
		"PORTAL_DRY_RUN":        "0",
	}
}

var jsonCT = map[string]string{"Content-Type": "application/json"}

func submit(form, body string) step {
	return step{Method: "POST", Path: "/api/submit/" + form, Headers: jsonCT, Body: body}
}

func photoData(mime string, n int) string {
	b := make([]byte, n)
	for i := range b {
		b[i] = byte(i % 251)
	}
	return "data:" + mime + ";base64," + base64.StdEncoding.EncodeToString(b)
}

func mustJSON(v any) string { return string(marshalJS(v)) }

// parityCases are the inputs. The expected outputs come from the Node capture.
func parityCases() []parityCase {
	volunteer := map[string]any{
		"name": "Maria Alvarez", "phone": "+1 (305) 555-0142", "date": "2026-11-07", "hours": "1.3", "met": "Kevin",
		"happened": "Homework help with @Tidepath Director and <b>fractions</b>.\nHe did well!", "urgent": "yes",
		"urgentText": "needs a laptop for school", "photo": photoData("image/jpeg", 3000),
	}
	volunteerNoPhoto := map[string]any{"name": "Leo Park", "date": "2026-11-06", "hours": 2, "happened": "Reading club", "urgent": "no"}
	workshop := map[string]any{
		"school": "Bayview Middle School", "contact": "Ana Lee", "email": "ana_lee@school.org", "phone": "305.555.0100",
		"dates": "Nov 18 or Nov 20, mornings", "grade": "7", "headcount": "60", "topic": "mental-health", "language": "English",
		"mode": "in-person", "notes": "Gym is free after 10 & we have a projector 📽️",
	}
	family := map[string]any{
		"parent": "Rosa Pérez", "email": "rosa@example.org", "language": "Spanish", "child": "Mateo", "age": "11",
		"school": "Bayview Middle School", "program": "family-counseling", "consent": "on",
	}
	approve := map[string]any{"request": "w004", "version": "V2", "decision": "approve", "name": "Ms. Lee"}
	changes := map[string]any{"request": "W004", "version": "v2", "decision": "changes", "comment": "Slide 3: use the school logo @everyone"}
	sanitize := map[string]any{
		"school": "  Bay\u200bview\u00a0 Middle \u0007School  ", "contact": "Jose\u0301 [Admin] `x` *y* ~z~ |q|", "email": "staff@escuela.edu",
		"dates": strings.Repeat("Monday or Tuesday ", 12), "grade": "6-8", "headcount": 1e2, "topic": "other", "topicOther": "Cyber@@safety and @@@mentions",
		"language": "Kreyòl ayisyen", "mode": "online", "notes": strings.Repeat("😀", 400),
	}
	familyBool := map[string]any{"parent": "P", "phone": "(786) 555-0199", "language": "Haitian Creole", "child": "Ti", "age": 3, "school": "S", "program": "mentoring", "consent": true}

	big := `{"name":"` + strings.Repeat("x", maxBody) + `"}`
	hugePhoto := mustJSON(map[string]any{"name": "A", "date": "2026-11-07", "hours": "1", "happened": "x", "photo": "data:image/jpeg;base64," + strings.Repeat("A", 6990508)})

	return []parityCase{
		{Name: "volunteer", Steps: []step{submit("volunteer", mustJSON(volunteer))}},
		{Name: "workshop", Steps: []step{submit("workshop", mustJSON(workshop))}},
		{Name: "family", Steps: []step{submit("family", mustJSON(family))}},
		{Name: "approve", Steps: []step{submit("approve", mustJSON(approve)), submit("approve", mustJSON(changes))}},
		{Name: "sanitize", Steps: []step{submit("workshop", mustJSON(sanitize)), submit("family", mustJSON(familyBool)), submit("volunteer", mustJSON(volunteerNoPhoto))}},
		{Name: "upload-and-lookup-fail", Env: map[string]string{"AGENT_VOLUNTEERS_NAME": "Volunteer Desk"},
			Responses: map[string]mockResponse{"images": {500, `{"error":{"message":"disk full"}}`}, "members": {503, "not json"}},
			Steps:     []step{submit("volunteer", mustJSON(volunteer))}},
		{Name: "agent-not-in-room", Responses: map[string]mockResponse{"members": {200, `{"data":[{"memberType":"agent","agentId":"other","displayName":"Someone Else"}]}`}},
			Steps: []step{submit("approve", mustJSON(approve))}},
		{Name: "upload-no-url", Responses: map[string]mockResponse{"images": {200, `{"ok":true}`}, "messages": {200, `{"message":{"id":"m-2"}}`}},
			Steps: []step{submit("volunteer", mustJSON(volunteer))}},
		{Name: "message-post-fails", Responses: map[string]mockResponse{"messages": {500, `{"message":"boom"}`}},
			Steps: []step{submit("family", mustJSON(family))}},
		{Name: "validation-errors", Steps: []step{
			submit("volunteer", `{"hours":"30","urgent":"yes","phone":"abc"}`),
			submit("workshop", `{"school":"X","contact":"Y","dates":"d","grade":"7","language":"English","email":"bad","headcount":"2.5","topic":"other"}`),
			submit("workshop", `{}`),
			submit("family", `{"phone":"12","email":"x@y","age":"30"}`),
			submit("family", `{"parent":"P","language":"Spanish","child":"C","school":"S","age":"9","program":"mentoring"}`),
			submit("approve", `{"request":"X1","version":"2","decision":"maybe"}`),
			submit("approve", `{"request":"W004","version":"v2","decision":"changes"}`),
		}},
		{Name: "photo-errors", Steps: []step{
			submit("volunteer", mustJSON(map[string]any{"name": "A", "date": "2026-11-07", "hours": "1", "happened": "x", "photo": "data:image/bmp;base64,QUJD"})),
			submit("volunteer", mustJSON(map[string]any{"name": "A", "date": "2026-11-07", "hours": "1", "happened": "x", "photo": "not a data url"})),
			submit("volunteer", hugePhoto),
		}},
		{Name: "request-errors", Steps: []step{
			{Method: "POST", Path: "/api/submit/volunteer", Headers: map[string]string{"Content-Type": "text/plain"}, Body: "{}"},
			{Method: "POST", Path: "/api/submit/volunteer", Body: "{}"},
			submit("volunteer", "[1,2]"),
			submit("volunteer", "null"),
			submit("volunteer", "not json"),
			submit("volunteer", `{"a":1} x`),
			submit("unknown", "{}"),
			submit("Volunteer", "{}"),
			{Method: "GET", Path: "/api/submit/volunteer"},
			{Method: "PUT", Path: "/api/submit/family", Headers: jsonCT, Body: "{}"},
			submit("approve", `{"website":"http://spam.example","request":"W004"}`),
			submit("volunteer", big),
		}},
		{Name: "not-configured", Env: map[string]string{"ROOM_PROGRAMS_ID": ""}, Steps: []step{
			{Method: "GET", Path: "/healthz"},
			submit("family", mustJSON(family)),
		}},
		{Name: "no-token", Env: map[string]string{"ROOMCORD_BOT_TOKEN": ""}, Steps: []step{
			{Method: "GET", Path: "/healthz"},
			submit("approve", mustJSON(approve)),
		}},
		{Name: "rate-limit", Env: map[string]string{"RATE_LIMIT_MAX": "2"}, Steps: []step{
			submit("approve", mustJSON(approve)),
			submit("approve", `{}`),
			submit("approve", mustJSON(approve)),
			submit("workshop", mustJSON(workshop)),
		}},
		{Name: "trust-proxy", Env: map[string]string{"RATE_LIMIT_MAX": "1", "TRUST_PROXY": "1"}, Steps: []step{
			{Method: "POST", Path: "/api/submit/approve", Headers: map[string]string{"Content-Type": "application/json", "X-Forwarded-For": "203.0.113.7"}, Body: mustJSON(approve)},
			{Method: "POST", Path: "/api/submit/approve", Headers: map[string]string{"Content-Type": "application/json", "X-Forwarded-For": "203.0.113.8, 10.0.0.1"}, Body: mustJSON(approve)},
			{Method: "POST", Path: "/api/submit/approve", Headers: map[string]string{"Content-Type": "application/json", "X-Forwarded-For": " 203.0.113.7 ,10.0.0.2"}, Body: mustJSON(approve)},
			{Method: "POST", Path: "/api/submit/approve", Headers: map[string]string{"Content-Type": "application/json; charset=utf-8"}, Body: mustJSON(approve)},
		}},
		{Name: "proxy-not-trusted", Env: map[string]string{"RATE_LIMIT_MAX": "1"}, Steps: []step{
			{Method: "POST", Path: "/api/submit/approve", Headers: map[string]string{"Content-Type": "application/json", "X-Forwarded-For": "203.0.113.7"}, Body: mustJSON(approve)},
			{Method: "POST", Path: "/api/submit/approve", Headers: map[string]string{"Content-Type": "application/json", "X-Forwarded-For": "203.0.113.8"}, Body: mustJSON(approve)},
		}},
		{Name: "dry-run", Env: map[string]string{"PORTAL_DRY_RUN": "1", "ROOMCORD_BOT_TOKEN": ""}, Steps: []step{
			{Method: "GET", Path: "/healthz"},
			submit("volunteer", mustJSON(volunteer)),
			submit("workshop", mustJSON(workshop)),
		}},
		{Name: "static", Steps: []step{
			{Method: "GET", Path: "/"},
			{Method: "GET", Path: "/index.html"},
			{Method: "GET", Path: "/volunteer"},
			{Method: "GET", Path: "/workshop"},
			{Method: "GET", Path: "/family"},
			{Method: "GET", Path: "/approve?request=W001&version=v2"},
			{Method: "GET", Path: "/thanks?form=volunteer&ref=TP-ABC123&lang=es"},
			{Method: "GET", Path: "/styles.css"},
			{Method: "GET", Path: "/app.js"},
			{Method: "GET", Path: "/i18n.js"},
			{Method: "GET", Path: "/favicon.svg"},
			{Method: "GET", Path: "/404.html"},
			{Method: "GET", Path: "/nope"},
			{Method: "GET", Path: "/volunteer/"},
			{Method: "GET", Path: "/styles.css/"},
			{Method: "GET", Path: "/a/../styles.css"},
			{Method: "GET", Path: "/%2e%2e/server.js"},
			{Method: "GET", Path: "/styles%2Ecss"},
			{Method: "GET", Path: "/healthz"},
			{Method: "POST", Path: "/healthz"},
			{Method: "HEAD", Path: "/"},
			{Method: "POST", Path: "/", Body: "x"},
			{Method: "DELETE", Path: "/styles.css"},
		}},
	}
}

// ---------- running a case ----------

var reRef = regexp.MustCompile(`TP-[0-9A-F]{6}`)

func doStep(t *testing.T, client *http.Client, base string, s step) *response {
	t.Helper()
	var body io.Reader
	if s.Body != "" {
		body = strings.NewReader(s.Body)
	}
	req, err := http.NewRequest(s.Method, base+s.Path, body)
	if err != nil {
		t.Fatal(err)
	}
	for k, v := range s.Headers {
		req.Header.Set(k, v)
	}
	res, err := client.Do(req)
	if err != nil {
		t.Fatalf("%s %s: %v", s.Method, s.Path, err)
	}
	defer res.Body.Close()
	data, _ := io.ReadAll(res.Body)
	out := &response{Status: res.StatusCode, Headers: map[string]string{}}
	for _, h := range recordedResponseHeaders {
		if v := res.Header.Get(h); v != "" {
			out.Headers[h] = v
		}
	}
	text := string(data)
	if strings.HasPrefix(res.Header.Get("Content-Type"), "application/json") {
		text = reRef.ReplaceAllString(text, "TP-<ref>")
	}
	out.Body = text
	return out
}

// bodyFiles replaces a body that equals a public file with its name, so the
// fixtures stay valid when the page content changes.
func useBodyFile(r *response, s step) {
	if r.Body == "" {
		return
	}
	var names []string
	fs.WalkDir(os.DirFS("public"), ".", func(p string, d fs.DirEntry, err error) error {
		if err == nil && !d.IsDir() {
			names = append(names, p)
		}
		return nil
	})
	sort.Strings(names)
	for _, n := range names {
		if b, err := os.ReadFile(filepath.Join("public", n)); err == nil && string(b) == r.Body {
			r.BodyFile, r.Body = n, ""
			return
		}
	}
}

func newTestClient() *http.Client {
	return &http.Client{
		Timeout:       30 * time.Second,
		Transport:     &http.Transport{DisableKeepAlives: true, DisableCompression: true},
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
	}
}

// ---------- capture from Node ----------

func freePort(t *testing.T) int {
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer l.Close()
	return l.Addr().(*net.TCPAddr).Port
}

func TestCaptureNodeGolden(t *testing.T) {
	serverJS := os.Getenv("PARITY_CAPTURE_NODE")
	if serverJS == "" {
		t.Skip("set PARITY_CAPTURE_NODE=/path/to/server.js to capture golden files from the Node server")
	}
	src, err := os.ReadFile(serverJS)
	if err != nil {
		t.Fatal(err)
	}
	os.MkdirAll("testdata/parity", 0o755)
	for _, c := range parityCases() {
		t.Run(c.Name, func(t *testing.T) {
			// A clean directory: no .env, so no real settings leak in.
			dir := t.TempDir()
			os.WriteFile(filepath.Join(dir, "server.js"), src, 0o644)
			if err := exec.Command("cp", "-R", "public", filepath.Join(dir, "public")).Run(); err != nil {
				t.Fatal(err)
			}
			mock := newMockRoomcord(t, c.Responses)
			port := freePort(t)
			env := []string{"PATH=" + os.Getenv("PATH"), "HOME=" + dir, fmt.Sprintf("PORT=%d", port)}
			for k, v := range mergeEnv(baseEnv(mock.URL), c.Env) {
				env = append(env, k+"="+v)
			}
			cmd := exec.Command("node", "server.js")
			cmd.Dir, cmd.Env = dir, env
			var logs bytes.Buffer
			cmd.Stdout, cmd.Stderr = &logs, &logs
			if err := cmd.Start(); err != nil {
				t.Fatal(err)
			}
			defer func() { cmd.Process.Kill(); cmd.Wait() }()
			base := fmt.Sprintf("http://127.0.0.1:%d", port)
			waitUp(t, base)
			client := newTestClient()
			for i := range c.Steps {
				r := doStep(t, client, base, c.Steps[i])
				useBodyFile(r, c.Steps[i])
				c.Steps[i].Expect = r
			}
			c.Roomcord = mock.requests()
			if c.Roomcord == nil {
				c.Roomcord = []recorded{}
			}
			out, _ := json.MarshalIndent(c, "", "  ")
			if err := os.WriteFile(filepath.Join("testdata/parity", c.Name+".json"), append(out, '\n'), 0o644); err != nil {
				t.Fatal(err)
			}
			t.Logf("node logs:\n%s", logs.String())
		})
	}
}

func mergeEnv(base, over map[string]string) map[string]string {
	for k, v := range over {
		base[k] = v
	}
	return base
}

func waitUp(t *testing.T, base string) {
	deadline := time.Now().Add(10 * time.Second)
	for time.Now().Before(deadline) {
		if res, err := http.Get(base + "/healthz"); err == nil {
			res.Body.Close()
			return
		}
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatal("server did not start")
}

// ---------- replay against Go ----------

func loadGolden(t *testing.T, name string) parityCase {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("testdata/parity", name+".json"))
	if err != nil {
		t.Fatalf("missing golden file (capture from Node first): %v", err)
	}
	var c parityCase
	if err := json.Unmarshal(data, &c); err != nil {
		t.Fatal(err)
	}
	return c
}

func startGo(t *testing.T, env map[string]string, logs io.Writer) *httptest.Server {
	static, _ := fs.Sub(embedded, "public")
	a := newApp(func(k string) string { return env[k] }, newLogger(logs), static)
	srv := httptest.NewServer(a)
	t.Cleanup(srv.Close)
	return srv
}

var knownDifferences = map[string]func(string) string{
	"sanitize": func(s string) string { return strings.ReplaceAll(s, `\ud83d…`, "…") },
}

func TestParity(t *testing.T) {
	for _, def := range parityCases() {
		t.Run(def.Name, func(t *testing.T) {
			golden := loadGolden(t, def.Name)
			if len(golden.Steps) != len(def.Steps) {
				t.Fatalf("golden file has %d steps, case has %d: capture again", len(golden.Steps), len(def.Steps))
			}
			mock := newMockRoomcord(t, golden.Responses)
			var logs bytes.Buffer
			srv := startGo(t, mergeEnv(baseEnv(mock.URL), golden.Env), &logs)
			client := newTestClient()
			for i, s := range golden.Steps {
				got := doStep(t, client, srv.URL, s)
				want := *s.Expect
				if want.BodyFile != "" {
					b, err := os.ReadFile(filepath.Join("public", want.BodyFile))
					if err != nil {
						t.Fatal(err)
					}
					want.Body = string(b)
				}
				if s.Method == "HEAD" {
					got.Body, want.Body = "", ""
				}
				want.BodyFile = ""
				if !reflect.DeepEqual(*got, want) {
					t.Errorf("step %d %s %s:\n got  %s\n want %s", i, s.Method, s.Path, short(got), short(&want))
				}
			}
			if fix := knownDifferences[def.Name]; fix != nil {
				for i := range golden.Roomcord {
					golden.Roomcord[i].Body = fix(golden.Roomcord[i].Body)
				}
			}
			gotReqs := mock.requests()
			if gotReqs == nil {
				gotReqs = []recorded{}
			}
			if !reflect.DeepEqual(gotReqs, golden.Roomcord) {
				g, _ := json.MarshalIndent(gotReqs, "", "  ")
				w, _ := json.MarshalIndent(golden.Roomcord, "", "  ")
				t.Errorf("Roomcord requests differ:\n got  %s\n want %s\nlogs:\n%s", g, w, logs.String())
			}
		})
	}
}

func short(r *response) string {
	c := *r
	if len(c.Body) > 300 {
		c.Body = c.Body[:300] + "..."
	}
	b, _ := json.Marshal(c)
	return string(b)
}
