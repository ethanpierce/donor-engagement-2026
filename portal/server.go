package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"io"
	"io/fs"
	"log/slog"
	"math"
	"net"
	"net/http"
	"path"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"
)

type config struct {
	port         int
	apiURL       string
	token        string
	rateMax      float64
	rateWindowMs float64
	trustProxy   bool
	dryRun       bool
	timeout      time.Duration // per outbound Roomcord request
}

// target is the room a form goes to and the specialist agent it mentions.
// agent is the room binding id that the room member list reports.
type target struct{ room, agent, agentName string }

type app struct {
	cfg     config
	targets map[string]target
	client  *http.Client
	log     *slog.Logger
	static  fs.FS
	names   nameCache
	limit   limiter
}

func orDefault(v, d string) string {
	if v == "" {
		return d
	}
	return v
}

func newApp(getenv func(string) string, log *slog.Logger, static fs.FS) *app {
	port := jsNumber(orDefault(getenv("PORT"), "8080"))
	cfg := config{
		port:         int(port),
		apiURL:       strings.TrimRight(getenv("ROOMCORD_API_URL"), "/"),
		token:        getenv("ROOMCORD_BOT_TOKEN"),
		rateMax:      jsNumber(orDefault(getenv("RATE_LIMIT_MAX"), "10")),
		rateWindowMs: jsNumber(orDefault(getenv("RATE_LIMIT_WINDOW_SEC"), "600")) * 1000,
		trustProxy:   getenv("TRUST_PROXY") == "1",
		dryRun:       getenv("PORTAL_DRY_RUN") == "1",
		timeout:      15 * time.Second,
	}
	if math.IsNaN(port) {
		cfg.port = -1
	}
	workshop := target{getenv("ROOM_WORKSHOPS_ID"), getenv("AGENT_WORKSHOPS_ID"), orDefault(getenv("AGENT_WORKSHOPS_NAME"), "Tidepath Workshops")}
	a := &app{
		cfg: cfg,
		targets: map[string]target{
			"volunteer": {getenv("ROOM_VOLUNTEERS_ID"), getenv("AGENT_VOLUNTEERS_ID"), orDefault(getenv("AGENT_VOLUNTEERS_NAME"), "Tidepath Volunteers")},
			"workshop":  workshop,
			"family":    {getenv("ROOM_PROGRAMS_ID"), getenv("AGENT_PROGRAMS_ID"), orDefault(getenv("AGENT_PROGRAMS_NAME"), "Tidepath Programs")},
			"approve":   workshop,
		},
		client: &http.Client{Timeout: cfg.timeout},
		log:    log,
		static: static,
		names:  nameCache{m: map[string]cachedName{}},
		limit:  limiter{hits: map[string][]int64{}},
	}
	return a
}

func (a *app) configured(formID string) bool {
	t, ok := a.targets[formID]
	return ok && a.cfg.apiURL != "" && (a.cfg.token != "" || a.cfg.dryRun) && t.room != "" && t.agent != ""
}

func (a *app) notConfigured() []string {
	missing := []string{}
	for _, f := range formOrder {
		if !a.configured(f) {
			missing = append(missing, f)
		}
	}
	return missing
}

// ---------- rate limit ----------

// limiter keeps a sliding window of post times (ms) per client IP.
type limiter struct {
	mu   sync.Mutex
	hits map[string][]int64
}

// rateLimited records a post and returns 0, or the seconds to wait when the IP is
// over the limit.
func (a *app) rateLimited(ip string) int {
	l := &a.limit
	l.mu.Lock()
	defer l.mu.Unlock()
	now := time.Now().UnixMilli()
	var list []int64
	for _, t := range l.hits[ip] {
		if float64(now-t) < a.cfg.rateWindowMs {
			list = append(list, t)
		}
	}
	if float64(len(list)) >= a.cfg.rateMax {
		l.hits[ip] = list
		if len(list) == 0 { // RATE_LIMIT_MAX=0: the Node server never limited
			return 0
		}
		w := math.Ceil((a.cfg.rateWindowMs - float64(now-list[0])) / 1000)
		if math.IsNaN(w) || w <= 0 {
			return 0
		}
		return int(w)
	}
	l.hits[ip] = append(list, now)
	return 0
}

// sweep drops IPs that have no posts left in the window.
func (a *app) sweep() {
	l := &a.limit
	l.mu.Lock()
	defer l.mu.Unlock()
	now := time.Now().UnixMilli()
	for ip, list := range l.hits {
		expired := true
		for _, t := range list {
			if !(float64(now-t) >= a.cfg.rateWindowMs) {
				expired = false
				break
			}
		}
		if expired {
			delete(l.hits, ip)
		}
	}
}

func (a *app) clientIP(r *http.Request) string {
	if a.cfg.trustProxy {
		if xff := strings.Join(r.Header.Values("X-Forwarded-For"), ", "); xff != "" {
			first, _, _ := strings.Cut(xff, ",")
			return jsTrim(first)
		}
	}
	if host, _, err := net.SplitHostPort(r.RemoteAddr); err == nil {
		return host
	}
	if r.RemoteAddr != "" {
		return r.RemoteAddr
	}
	return "unknown"
}

// ---------- HTTP ----------

var contentTypes = map[string]string{
	".html":        "text/html; charset=utf-8",
	".css":         "text/css; charset=utf-8",
	".js":          "text/javascript; charset=utf-8",
	".svg":         "image/svg+xml",
	".png":         "image/png",
	".ico":         "image/x-icon",
	".webmanifest": "application/manifest+json",
}

var pages = map[string]string{"/": "index.html", "/volunteer": "volunteer.html", "/workshop": "workshop.html", "/family": "family.html", "/approve": "approve.html", "/thanks": "thanks.html"}

var securityHeaders = [][2]string{
	{"X-Content-Type-Options", "nosniff"},
	{"Referrer-Policy", "no-referrer"},
	{"X-Frame-Options", "DENY"},
	{"Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob:; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"},
}

var reSubmit = regexp.MustCompile(`^/api/submit/([a-z]+)$`)

// send writes a response with the security headers. headers are name/value
// pairs. Without a Content-Type pair the response has no Content-Type.
func send(w http.ResponseWriter, status int, body []byte, headers ...string) {
	h := w.Header()
	for _, kv := range securityHeaders {
		h.Set(kv[0], kv[1])
	}
	h["Content-Type"] = nil // no sniffed type, as in Node
	for i := 0; i+1 < len(headers); i += 2 {
		h.Set(headers[i], headers[i+1])
	}
	h.Set("Content-Length", strconv.Itoa(len(body)))
	w.WriteHeader(status)
	w.Write(body)
}

type apiResponse struct {
	OK         bool    `json:"ok"`
	Error      string  `json:"error,omitempty"`
	Ref        string  `json:"ref,omitempty"`
	RetryAfter int     `json:"retryAfter,omitempty"`
	Fields     ordered `json:"fields,omitempty"`
	Forms      ordered `json:"forms,omitempty"`
}

func sendJSON(w http.ResponseWriter, status int, data any, headers ...string) {
	headers = append([]string{"Content-Type", "application/json; charset=utf-8", "Cache-Control", "no-store"}, headers...)
	send(w, status, marshalJS(data), headers...)
}

type statusError struct{ status int }

func (e statusError) Error() string { return "status " + strconv.Itoa(e.status) }

func readJSON(r *http.Request) (map[string]any, error) {
	if !strings.HasPrefix(r.Header.Get("Content-Type"), "application/json") {
		return nil, statusError{415}
	}
	raw, err := io.ReadAll(io.LimitReader(r.Body, maxBody+1))
	if err != nil {
		return nil, statusError{400}
	}
	if len(raw) > maxBody {
		return nil, statusError{413}
	}
	v, ok := parseJSON(raw)
	m, isObj := v.(map[string]any)
	if !ok || !isObj {
		return nil, statusError{400}
	}
	return m, nil
}

func newRef() string {
	b := make([]byte, 3)
	rand.Read(b)
	return "TP-" + strings.ToUpper(hex.EncodeToString(b))
}

func (a *app) handleSubmit(w http.ResponseWriter, r *http.Request, formID string) {
	f, ok := forms[formID]
	if !ok {
		sendJSON(w, 404, apiResponse{Error: "unknown_form"})
		return
	}
	if !a.configured(formID) {
		sendJSON(w, 503, apiResponse{Error: "not_configured"})
		return
	}
	if wait := a.rateLimited(a.clientIP(r)); wait > 0 {
		sendJSON(w, 429, apiResponse{Error: "rate_limited", RetryAfter: wait}, "Retry-After", strconv.Itoa(wait))
		return
	}
	body, err := readJSON(r)
	if err != nil {
		var se statusError
		errors.As(err, &se)
		msg := "bad_request"
		if se.status == 413 {
			msg = "too_large"
		}
		sendJSON(w, se.status, apiResponse{Error: msg})
		return
	}
	if jsTruthy(body["website"]) { // honeypot: pretend success
		sendJSON(w, 200, apiResponse{OK: true, Ref: newRef()})
		return
	}
	errs, fields := f.validate(body)
	if len(errs) > 0 {
		sendJSON(w, 400, apiResponse{Error: "invalid", Fields: errs})
		return
	}
	ref := newRef()
	var photo any
	if formID == "volunteer" {
		photo = body["photo"]
	}
	id, err := a.post(r.Context(), formID, fields, photo)
	if err != nil {
		var pe photoError
		if errors.As(err, &pe) {
			sendJSON(w, 400, apiResponse{Error: "invalid", Fields: ordered{{"photo", pe.code}}})
			return
		}
		attrs := []any{"form", formID, "ref", ref, "error", err.Error()}
		var ue *upstreamError
		if errors.As(err, &ue) {
			attrs = append(attrs, "detail", ue.detail)
		}
		a.log.Error("post failed", attrs...)
		sendJSON(w, 502, apiResponse{Error: "upstream"})
		return
	}
	a.log.Info("posted", "form", formID, "ref", ref, "message", id)
	sendJSON(w, 200, apiResponse{OK: true, Ref: ref})
}

// requestPath is the WHATWG URL pathname: still percent-encoded, with dot
// segments resolved.
func requestPath(r *http.Request) string {
	p := r.URL.EscapedPath()
	if p == "" || p[0] != '/' {
		p = "/" + p
	}
	segs := strings.Split(p[1:], "/")
	var out []string
	trailing := false
	for i, s := range segs {
		last := i == len(segs)-1
		switch strings.ToLower(s) {
		case ".", "%2e":
			trailing = last
		case "..", ".%2e", "%2e.", "%2e%2e":
			if len(out) > 0 {
				out = out[:len(out)-1]
			}
			trailing = last
		default:
			out = append(out, s)
			trailing = false
		}
	}
	res := "/" + strings.Join(out, "/")
	if trailing && res != "/" {
		res += "/"
	}
	return res
}

func (a *app) serveStatic(w http.ResponseWriter, r *http.Request, p string) {
	name, ok := pages[p]
	if !ok {
		name = p[1:]
	}
	if data, err := fs.ReadFile(a.static, name); err == nil && fs.ValidPath(name) {
		ctype := contentTypes[path.Ext(name)]
		if ctype == "" {
			ctype = "application/octet-stream"
		}
		cache := "public, max-age=300"
		if strings.HasPrefix(ctype, "text/html") {
			cache = "no-cache"
		}
		send(w, 200, data, "Content-Type", ctype, "Cache-Control", cache)
		return
	}
	page, err := fs.ReadFile(a.static, "404.html")
	if err != nil {
		page = []byte("Not found")
	}
	send(w, 404, page, "Content-Type", "text/html; charset=utf-8")
}

func (a *app) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	rw := &trackingWriter{ResponseWriter: w}
	defer func() {
		if v := recover(); v != nil {
			if v == http.ErrAbortHandler {
				panic(v)
			}
			a.log.Error("unhandled", "error", slog.AnyValue(v).String())
			if !rw.wrote {
				sendJSON(rw, 500, apiResponse{Error: "server"})
			}
		}
	}()
	p := requestPath(r)
	if p == "/healthz" {
		var f ordered
		for _, id := range formOrder {
			f = append(f, kv{id, a.configured(id)})
		}
		sendJSON(rw, 200, apiResponse{OK: true, Forms: f})
		return
	}
	if m := reSubmit.FindStringSubmatch(p); m != nil {
		if r.Method != http.MethodPost {
			sendJSON(rw, 405, apiResponse{Error: "method"}, "Allow", "POST")
			return
		}
		a.handleSubmit(rw, r, m[1])
		return
	}
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		send(rw, 405, []byte("Method not allowed"), "Allow", "GET, HEAD")
		return
	}
	a.serveStatic(rw, r, p)
}

type trackingWriter struct {
	http.ResponseWriter
	wrote bool
}

func (t *trackingWriter) WriteHeader(code int) {
	t.wrote = true
	t.ResponseWriter.WriteHeader(code)
}

// startSweeper drops expired rate-limit entries every minute until ctx ends.
func (a *app) startSweeper(ctx context.Context) {
	go func() {
		tick := time.NewTicker(time.Minute)
		defer tick.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-tick.C:
				a.sweep()
			}
		}
	}()
}
