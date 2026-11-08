package main

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"net/textproto"
	"regexp"
	"strings"
	"sync"
	"time"
)

const (
	maxBody  = 8 * 1024 * 1024 // JSON body, includes an optional base64 photo
	maxPhoto = 5 * 1024 * 1024
)

var photoTypes = map[string]string{"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}

var rePhoto = regexp.MustCompile(`^data:(image/[a-z]+);base64,([A-Za-z0-9+/=]+)$`)

// photoError is a problem with the visitor's file. The visitor sees it.
type photoError struct{ code string }

func (e photoError) Error() string { return "bad photo: " + e.code }

type upstreamError struct {
	msg    string
	detail string
}

func (e *upstreamError) Error() string { return e.msg }

type multipartBody struct {
	data        []byte
	contentType string
}

// roomcord calls the Roomcord API. body is nil, a multipartBody, or a value
// sent as JSON. It returns the decoded JSON response, {} when empty.
func (a *app) roomcord(ctx context.Context, method, path string, body any) (any, error) {
	var rd io.Reader
	ctype := ""
	switch b := body.(type) {
	case nil:
	case multipartBody:
		rd, ctype = bytes.NewReader(b.data), b.contentType
	default:
		rd, ctype = bytes.NewReader(marshalJS(b)), "application/json"
	}
	req, err := http.NewRequestWithContext(ctx, method, a.cfg.apiURL+path, rd)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+a.cfg.token)
	if ctype != "" {
		req.Header.Set("Content-Type", ctype)
	}
	res, err := a.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer res.Body.Close()
	text, err := io.ReadAll(io.LimitReader(res.Body, 1<<20))
	if err != nil {
		return nil, err
	}
	var data any = map[string]any{}
	if len(text) > 0 {
		if v, ok := parseJSON(text); ok {
			data = v
		} else {
			data = map[string]any{"raw": utf16Prefix(string(text), 200)}
		}
	}
	if res.StatusCode < 200 || res.StatusCode > 299 {
		p, _, _ := strings.Cut(path, "?")
		detail := firstTruthy(get(get(data, "error"), "message"), get(data, "message"), "")
		return nil, &upstreamError{msg: fmt.Sprintf("Roomcord %s %s -> %d", method, p, res.StatusCode), detail: jsString(detail)}
	}
	return data, nil
}

// nameCache keeps the agent display name per room for 10 minutes.
type nameCache struct {
	mu sync.Mutex
	m  map[string]cachedName
}

type cachedName struct {
	name string
	at   time.Time
}

// agentName returns the visible @Name. It must match the agent's display name
// in the room, so Roomcord resolves the mention. Look it up by binding id and
// cache it. Fall back to the configured name when the lookup fails.
func (a *app) agentName(ctx context.Context, t target) string {
	key := t.room + ":" + t.agent
	a.names.mu.Lock()
	hit, ok := a.names.m[key]
	a.names.mu.Unlock()
	if ok && time.Since(hit.at) < 10*time.Minute {
		return hit.name
	}
	name := t.agentName
	res, err := a.roomcord(ctx, "GET", "/rooms/"+encodeURIComponent(t.room)+"/members?limit=200", nil)
	if err == nil {
		var display any
		display, err = findAgent(res, t.agent)
		if err == nil {
			if jsTruthy(display) {
				name = jsString(display)
			} else {
				a.log.Warn("agent not found in room members, using configured name", "room", t.room)
			}
		}
	}
	if err != nil {
		a.log.Warn("member lookup failed, using configured name", "error", err.Error())
	}
	a.names.mu.Lock()
	a.names.m[key] = cachedName{name, time.Now()}
	a.names.mu.Unlock()
	return name
}

// findAgent is (res.data || []).find(agent with this binding id)?.displayName.
// It fails where the JavaScript expression throws a TypeError.
func findAgent(res any, agentID string) (any, error) {
	if res == nil {
		return nil, errors.New("member list response is null")
	}
	list := get(res, "data")
	if !jsTruthy(list) {
		return nil, nil
	}
	items, ok := list.([]any)
	if !ok {
		return nil, errors.New("member list is not an array")
	}
	for _, x := range items {
		if x == nil {
			return nil, errors.New("member list has a null entry")
		}
		if strIs(get(x, "memberType"), "agent") && strIs(get(x, "agentId"), agentID) {
			return get(x, "displayName"), nil
		}
	}
	return nil, nil
}

// decodeBase64Lenient decodes like Node's Buffer.from(s, "base64"): it stops
// at the first "=" and drops a final partial group of one character.
func decodeBase64Lenient(s string) []byte {
	if i := strings.IndexByte(s, '='); i >= 0 {
		s = s[:i]
	}
	if len(s)%4 == 1 {
		s = s[:len(s)-1]
	}
	out := make([]byte, 0, len(s)*3/4)
	const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
	var acc uint32
	bits := 0
	for i := 0; i < len(s); i++ {
		acc = acc<<6 | uint32(strings.IndexByte(alphabet, s[i]))
		bits += 6
		if bits >= 8 {
			bits -= 8
			out = append(out, byte(acc>>bits))
		}
	}
	return out
}

func (a *app) uploadPhoto(ctx context.Context, room string, photo any) (any, error) {
	m := rePhoto.FindStringSubmatch(jsString(photo))
	if m == nil || photoTypes[m[1]] == "" {
		return nil, photoError{"photo"}
	}
	buf := decodeBase64Lenient(m[2])
	if len(buf) > maxPhoto {
		return nil, photoError{"photoSize"}
	}
	var body bytes.Buffer
	w := multipart.NewWriter(&body)
	h := textproto.MIMEHeader{}
	h.Set("Content-Disposition", fmt.Sprintf(`form-data; name="image"; filename="checkin.%s"`, photoTypes[m[1]]))
	h.Set("Content-Type", m[1])
	pw, err := w.CreatePart(h)
	if err != nil {
		return nil, err
	}
	pw.Write(buf)
	w.Close()
	res, err := a.roomcord(ctx, "POST", "/rooms/"+encodeURIComponent(room)+"/images", multipartBody{body.Bytes(), w.FormDataContentType()})
	if err != nil {
		return nil, err
	}
	d := get(res, "data")
	url := firstTruthy(get(res, "url"), get(res, "imageUrl"), get(d, "url"), get(d, "imageUrl"))
	if !jsTruthy(url) {
		return nil, errors.New("upload returned no url")
	}
	return url, nil
}

type messageBody struct {
	Content        string `json:"content"`
	Type           string `json:"type"`
	AttachmentUrls []any  `json:"attachmentUrls,omitempty"`
}

// post sends one form to its room. It returns the Roomcord message id.
func (a *app) post(ctx context.Context, formID string, fields map[string]string, photo any) (string, error) {
	t := a.targets[formID]
	var x extra
	var attachments []any
	if jsTruthy(photo) {
		url, err := a.uploadPhoto(ctx, t.room, photo)
		var pe photoError
		switch {
		case err == nil:
			attachments = append(attachments, url)
			x.photo = true
		case errors.As(err, &pe):
			return "", err // the visitor's file is bad: tell them
		default:
			a.log.Warn("photo upload failed, posting without it", "error", err.Error())
			x.photoSkipped = true
		}
	}
	text := forms[formID].format(fields, x)
	name := a.agentName(ctx, t)
	body := messageBody{Content: "@" + name + " " + text, Type: "text", AttachmentUrls: attachments}
	if a.cfg.dryRun {
		a.log.Info("dry run, not posted", "form", formID, "content", body.Content)
		return "dry-run", nil
	}
	res, err := a.roomcord(ctx, "POST", "/rooms/"+encodeURIComponent(t.room)+"/messages", body)
	if err != nil {
		return "", err
	}
	if res == nil {
		return "", errors.New("message response is null")
	}
	id := firstTruthy(get(res, "id"), get(get(res, "data"), "id"), get(get(res, "message"), "id"), "")
	return jsString(id), nil
}
