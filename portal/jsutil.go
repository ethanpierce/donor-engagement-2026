package main

// Helpers that reproduce the JavaScript semantics the Node server relied on:
// String(value), Number(text), truthiness, UTF-16 string length,
// encodeURIComponent and JSON.stringify output.

import (
	"bytes"
	"encoding/json"
	"math"
	"regexp"
	"strconv"
	"strings"
	"unicode/utf16"
)

// jsSpace is the set that JavaScript \s and String.prototype.trim use.
const jsSpaceClass = `\t\n\v\f\r \x{a0}\x{1680}\x{2000}-\x{200a}\x{2028}\x{2029}\x{202f}\x{205f}\x{3000}\x{feff}`

func isJSSpace(r rune) bool {
	switch r {
	case '\t', '\n', '\v', '\f', '\r', ' ', 0xa0, 0x1680, 0x2028, 0x2029, 0x202f, 0x205f, 0x3000, 0xfeff:
		return true
	}
	return r >= 0x2000 && r <= 0x200a
}

func jsTrim(s string) string { return strings.TrimFunc(s, isJSSpace) }

// jsString is String(v) for a value decoded from JSON (decoder.UseNumber).
func jsString(v any) string {
	switch x := v.(type) {
	case nil:
		return "null"
	case string:
		return x
	case bool:
		if x {
			return "true"
		}
		return "false"
	case json.Number:
		f, _ := strconv.ParseFloat(string(x), 64)
		return jsNumberString(f)
	case float64:
		return jsNumberString(x)
	case []any:
		parts := make([]string, len(x))
		for i, e := range x {
			if e != nil {
				parts[i] = jsString(e)
			}
		}
		return strings.Join(parts, ",")
	default:
		return "[object Object]"
	}
}

// jsTruthy is the JavaScript truthiness of a JSON value.
func jsTruthy(v any) bool {
	switch x := v.(type) {
	case nil:
		return false
	case string:
		return x != ""
	case bool:
		return x
	case json.Number:
		f, _ := strconv.ParseFloat(string(x), 64)
		return f != 0 && !math.IsNaN(f)
	case float64:
		return x != 0 && !math.IsNaN(x)
	default:
		return true
	}
}

// jsNumberString is Number.prototype.toString() for base 10.
func jsNumberString(f float64) string {
	switch {
	case math.IsNaN(f):
		return "NaN"
	case math.IsInf(f, 1):
		return "Infinity"
	case math.IsInf(f, -1):
		return "-Infinity"
	case f == 0:
		return "0"
	}
	if a := math.Abs(f); a >= 1e21 || a < 1e-6 {
		s := strconv.FormatFloat(f, 'e', -1, 64) // 1.5e-07
		mant, exp, _ := strings.Cut(s, "e")
		sign, digits := exp[:1], strings.TrimLeft(exp[1:], "0")
		return mant + "e" + sign + digits
	}
	return strconv.FormatFloat(f, 'f', -1, 64)
}

var reJSDecimal = regexp.MustCompile(`^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$`)

// jsNumber is Number(s) for a string.
func jsNumber(s string) float64 {
	s = jsTrim(s)
	switch s {
	case "":
		return 0
	case "Infinity", "+Infinity":
		return math.Inf(1)
	case "-Infinity":
		return math.Inf(-1)
	}
	if len(s) > 2 && s[0] == '0' {
		base := 0
		switch s[1] {
		case 'x', 'X':
			base = 16
		case 'o', 'O':
			base = 8
		case 'b', 'B':
			base = 2
		}
		if base != 0 {
			n, err := strconv.ParseUint(s[2:], base, 64)
			if err != nil || strings.Contains(s[2:], "_") {
				return math.NaN()
			}
			return float64(n)
		}
	}
	if !reJSDecimal.MatchString(s) {
		return math.NaN()
	}
	f, _ := strconv.ParseFloat(s, 64) // out of range gives +-Inf, as in JS
	return f
}

func jsIsInteger(f float64) bool {
	return !math.IsInf(f, 0) && !math.IsNaN(f) && f == math.Trunc(f)
}

// utf16Len is String.prototype.length.
func utf16Len(s string) int {
	n := 0
	for _, r := range s {
		if r >= 0x10000 {
			n += 2
		} else {
			n++
		}
	}
	return n
}

// utf16Prefix is s.slice(0, n) in UTF-16 units. A surrogate pair cut in
// half is dropped, because Go strings cannot hold a lone surrogate.
func utf16Prefix(s string, n int) string {
	u := utf16.Encode([]rune(s))
	if len(u) <= n {
		return s
	}
	u = u[:n]
	if k := len(u); k > 0 && u[k-1] >= 0xd800 && u[k-1] < 0xdc00 {
		u = u[:k-1]
	}
	return string(utf16.Decode(u))
}

// encodeURIComponent keeps A-Z a-z 0-9 - _ . ! ~ * ' ( ) and escapes the rest.
func encodeURIComponent(s string) string {
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c >= 'A' && c <= 'Z' || c >= 'a' && c <= 'z' || c >= '0' && c <= '9' || strings.IndexByte("-_.!~*'()", c) >= 0 {
			b.WriteByte(c)
		} else {
			b.WriteString("%" + strings.ToUpper(strconv.FormatUint(uint64(c)|0x100, 16)[1:]))
		}
	}
	return b.String()
}

// marshalJS is JSON.stringify for plain data: no HTML escaping, no newline.
func marshalJS(v any) []byte {
	var b bytes.Buffer
	enc := json.NewEncoder(&b)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(v); err != nil {
		panic(err)
	}
	return bytes.TrimSuffix(b.Bytes(), []byte("\n"))
}

// ordered is a JSON object that keeps insertion order, like a JS object
// with string keys. Setting an existing key keeps its position.
type ordered []kv

type kv struct {
	k string
	v any
}

func (o *ordered) set(k string, v any) {
	for i := range *o {
		if (*o)[i].k == k {
			(*o)[i].v = v
			return
		}
	}
	*o = append(*o, kv{k, v})
}

func (o ordered) MarshalJSON() ([]byte, error) {
	var b bytes.Buffer
	b.WriteByte('{')
	for i, e := range o {
		if i > 0 {
			b.WriteByte(',')
		}
		b.Write(marshalJS(e.k))
		b.WriteByte(':')
		b.Write(marshalJS(e.v))
	}
	b.WriteByte('}')
	return b.Bytes(), nil
}

// parseJSON is JSON.parse: one value, numbers kept as json.Number.
func parseJSON(text []byte) (any, bool) {
	if !json.Valid(text) {
		return nil, false
	}
	dec := json.NewDecoder(bytes.NewReader(text))
	dec.UseNumber()
	var v any
	if dec.Decode(&v) != nil {
		return nil, false
	}
	return v, true
}

// get reads obj[key] when v is a JSON object, else nil (like obj?.key).
func get(v any, key string) any {
	if m, ok := v.(map[string]any); ok {
		return m[key]
	}
	return nil
}

// firstTruthy is a || b || c.
func firstTruthy(vs ...any) any {
	for _, v := range vs {
		if jsTruthy(v) {
			return v
		}
	}
	return vs[len(vs)-1]
}
