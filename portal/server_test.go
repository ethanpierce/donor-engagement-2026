package main

// Go-only behavior that the Node capture cannot show.

import (
	"bytes"
	"context"
	"fmt"
	"io/fs"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"
)

func testApp(t *testing.T, mock *mockRoomcord, over map[string]string, logs *bytes.Buffer) (*app, *httptest.Server) {
	static, _ := fs.Sub(embedded, "public")
	env := mergeEnv(baseEnv(mock.URL), over)
	a := newApp(func(k string) string { return env[k] }, newLogger(logs), static)
	srv := httptest.NewServer(a)
	t.Cleanup(srv.Close)
	return a, srv
}

const approveJSON = `{"request":"W004","version":"v2","decision":"approve"}`

func postJSON(t *testing.T, url, body string) (int, string) {
	res, err := http.Post(url, "application/json", strings.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	defer res.Body.Close()
	var b bytes.Buffer
	b.ReadFrom(res.Body)
	return res.StatusCode, b.String()
}

// Node answered a Roomcord timeout with 400 {fields:{photo:23}} because the
// AbortSignal error has a numeric code. Go answers 502 upstream.
func TestUpstreamTimeoutIs502(t *testing.T) {
	slow := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { time.Sleep(500 * time.Millisecond) }))
	defer slow.Close()
	mock := &mockRoomcord{Server: slow}
	var logs bytes.Buffer
	a, srv := testApp(t, mock, nil, &logs)
	a.client.Timeout = 100 * time.Millisecond
	code, body := postJSON(t, srv.URL+"/api/submit/approve", approveJSON)
	if code != 502 || body != `{"ok":false,"error":"upstream"}` {
		t.Fatalf("got %d %s", code, body)
	}
	if !strings.Contains(logs.String(), "member lookup failed") {
		t.Fatalf("expected fallback log, got %s", logs.String())
	}
}

func TestAgentNameIsCached(t *testing.T) {
	mock := newMockRoomcord(t, nil)
	var logs bytes.Buffer
	_, srv := testApp(t, mock, nil, &logs)
	for i := 0; i < 3; i++ {
		if code, body := postJSON(t, srv.URL+"/api/submit/approve", approveJSON); code != 200 {
			t.Fatalf("got %d %s", code, body)
		}
	}
	lookups := 0
	for _, r := range mock.requests() {
		if strings.Contains(r.Path, "/members") {
			lookups++
		}
	}
	if lookups != 1 {
		t.Fatalf("member lookups = %d, want 1", lookups)
	}
}

func TestLogsAreJSONLinesWithoutToken(t *testing.T) {
	mock := newMockRoomcord(t, nil)
	var logs bytes.Buffer
	_, srv := testApp(t, mock, map[string]string{"PORTAL_DRY_RUN": "1"}, &logs)
	postJSON(t, srv.URL+"/api/submit/approve", approveJSON)
	out := logs.String()
	if !strings.HasPrefix(out, `{"t":"`) || !strings.Contains(out, `"level":"info","msg":"dry run, not posted","form":"approve","content":"@Workshops Agent School approved W004 v2. Sent from the Portal."`) {
		t.Fatalf("unexpected log: %s", out)
	}
	if strings.Contains(out, fakeToken) {
		t.Fatal("token in logs")
	}
}

func TestRateLimitZeroMeansNoLimit(t *testing.T) {
	mock := newMockRoomcord(t, nil)
	var logs bytes.Buffer
	_, srv := testApp(t, mock, map[string]string{"RATE_LIMIT_MAX": "0"}, &logs)
	for i := 0; i < 3; i++ {
		if code, _ := postJSON(t, srv.URL+"/api/submit/approve", approveJSON); code != 200 {
			t.Fatalf("request %d got %d", i, code)
		}
	}
}

func TestSweepDropsExpiredIPs(t *testing.T) {
	mock := newMockRoomcord(t, nil)
	a, _ := testApp(t, mock, nil, &bytes.Buffer{})
	a.limit.hits["1.2.3.4"] = []int64{time.Now().Add(-11 * time.Minute).UnixMilli()}
	a.limit.hits["5.6.7.8"] = []int64{time.Now().UnixMilli()}
	a.sweep()
	if _, ok := a.limit.hits["1.2.3.4"]; ok {
		t.Fatal("expired IP kept")
	}
	if _, ok := a.limit.hits["5.6.7.8"]; !ok {
		t.Fatal("active IP dropped")
	}
}

func TestGracefulShutdown(t *testing.T) {
	mock := newMockRoomcord(t, nil)
	env := mergeEnv(baseEnv(mock.URL), map[string]string{"PORT": fmt.Sprint(freePort(t))})
	static, _ := fs.Sub(embedded, "public")
	var logs bytes.Buffer
	a := newApp(func(k string) string { return env[k] }, newLogger(&logs), static)
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() { done <- a.run(ctx) }()
	waitUp(t, "http://127.0.0.1:"+env["PORT"])
	cancel()
	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("run returned %v", err)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("server did not stop")
	}
	if !strings.Contains(logs.String(), `"msg":"Tidepath portal on :`+env["PORT"]+`","dryRun":false,"notConfigured":[]`) {
		t.Fatalf("missing start log: %s", logs.String())
	}
}

func TestLoadDotEnvKeepsSetVariables(t *testing.T) {
	dir := t.TempDir()
	file := dir + "/.env"
	writeFile(t, file, "# comment\nTP_TEST_A = 'one' \r\nTP_TEST_B=\"two\"\nTP_TEST_C=three\nlower=x\n")
	t.Setenv("TP_TEST_C", "set")
	t.Setenv("TP_TEST_A", "")
	loadDotEnv(file)
	for k, want := range map[string]string{"TP_TEST_A": "", "TP_TEST_B": "two", "TP_TEST_C": "set"} {
		if got := getenvT(k); got != want {
			t.Errorf("%s = %q, want %q", k, got, want)
		}
	}
}

func writeFile(t *testing.T, name, content string) {
	t.Helper()
	if err := os.WriteFile(name, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
	os.Unsetenv("TP_TEST_B")
	t.Cleanup(func() { os.Unsetenv("TP_TEST_B") })
}

func getenvT(k string) string { return os.Getenv(k) }
