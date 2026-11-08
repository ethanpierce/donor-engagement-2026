package main

import (
	"crypto/sha256"
	"encoding/hex"
	"io"
	"mime"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
)

// Fixed ids that every test uses. They are fake.
const (
	roomVolunteers = "11111111-1111-4111-8111-111111111111"
	roomWorkshops  = "22222222-2222-4222-8222-222222222222"
	roomPrograms   = "33333333-3333-4333-8333-333333333333"
	agentVolunteer = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
	agentWorkshops = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
	agentPrograms  = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
	fakeToken      = "test-token-not-real"
)

var roomAgents = map[string][2]string{
	roomVolunteers: {agentVolunteer, "Volunteers Agent"},
	roomWorkshops:  {agentWorkshops, "Workshops Agent"},
	roomPrograms:   {agentPrograms, "Programs Agent"},
}

// recorded is one request that reached the mock Roomcord API.
// The multipart boundary is random, so Content-Type shows <boundary>.
type recorded struct {
	Method  string            `json:"method"`
	Path    string            `json:"path"`
	Headers map[string]string `json:"headers"`
	Body    string            `json:"body,omitempty"`
	Parts   []recordedPart    `json:"parts,omitempty"`
}

type recordedPart struct {
	Disposition string `json:"contentDisposition"`
	ContentType string `json:"contentType"`
	Size        int    `json:"size"`
	SHA256      string `json:"sha256"`
}

type mockResponse struct {
	Status int    `json:"status"`
	Body   string `json:"body"`
}

// mockRoomcord is an httptest Roomcord API under /api/v1. responses
// overrides the reply for "members", "images" or "messages".
type mockRoomcord struct {
	*httptest.Server
	mu        sync.Mutex
	reqs      []recorded
	responses map[string]mockResponse
}

func newMockRoomcord(t testing.TB, responses map[string]mockResponse) *mockRoomcord {
	m := &mockRoomcord{responses: responses}
	m.Server = httptest.NewServer(http.HandlerFunc(m.serve))
	t.Cleanup(m.Close)
	return m
}

func (m *mockRoomcord) requests() []recorded {
	m.mu.Lock()
	defer m.mu.Unlock()
	return append([]recorded(nil), m.reqs...)
}

func (m *mockRoomcord) serve(w http.ResponseWriter, r *http.Request) {
	rec := recorded{Method: r.Method, Path: r.URL.RequestURI(), Headers: map[string]string{}}
	for _, h := range []string{"Authorization", "Content-Type"} {
		if v := r.Header.Get(h); v != "" {
			rec.Headers[h] = v
		}
	}
	mt, params, _ := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if mt == "multipart/form-data" {
		rec.Headers["Content-Type"] = strings.Replace(rec.Headers["Content-Type"], params["boundary"], "<boundary>", 1)
		mr := multipart.NewReader(r.Body, params["boundary"])
		for {
			p, err := mr.NextRawPart()
			if err != nil {
				break
			}
			data, _ := io.ReadAll(p)
			sum := sha256.Sum256(data)
			rec.Parts = append(rec.Parts, recordedPart{p.Header.Get("Content-Disposition"), p.Header.Get("Content-Type"), len(data), hex.EncodeToString(sum[:])})
		}
	} else {
		b, _ := io.ReadAll(r.Body)
		rec.Body = string(b)
	}
	m.mu.Lock()
	m.reqs = append(m.reqs, rec)
	m.mu.Unlock()

	parts := strings.Split(strings.TrimPrefix(r.URL.Path, "/api/v1/"), "/")
	if len(parts) != 3 || parts[0] != "rooms" {
		http.Error(w, `{"error":{"message":"no route"}}`, 404)
		return
	}
	room, kind := parts[1], parts[2]
	resp := mockResponse{Status: 404, Body: `{"error":{"message":"no route"}}`}
	agent := roomAgents[room]
	switch {
	case kind == "members" && r.Method == "GET":
		resp = mockResponse{200, `{"data":[{"memberType":"user","userId":"u-1","displayName":"Ana Staff"},{"memberType":"agent","agentId":"` + agent[0] + `","displayName":"` + agent[1] + `"}]}`}
	case kind == "images" && r.Method == "POST":
		resp = mockResponse{201, `{"data":{"url":"https://cdn.example.test/rooms/` + room + `/img-1.jpg"}}`}
	case kind == "messages" && r.Method == "POST":
		resp = mockResponse{201, `{"data":{"id":"msg-1"}}`}
	}
	if o, ok := m.responses[kind]; ok {
		resp = o
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(resp.Status)
	io.WriteString(w, resp.Body)
}
