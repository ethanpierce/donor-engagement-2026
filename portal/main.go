// Tidepath portal: public forms that post into Roomcord rooms.
// Configure with environment variables only. A local .env file in the
// working directory is read too. Variables that are already set win.
package main

import (
	"context"
	"embed"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"regexp"
	"strings"
	"syscall"
	"time"
)

//go:embed public
var embedded embed.FS

func main() {
	if len(os.Args) > 1 && os.Args[1] == "-healthcheck" {
		os.Exit(healthcheck())
	}
	loadDotEnv(".env")
	log := newLogger(os.Stdout)
	static, _ := fs.Sub(embedded, "public")
	a := newApp(os.Getenv, log, static)

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	if err := a.run(ctx); err != nil {
		log.Error("server failed", "error", err.Error())
		os.Exit(1)
	}
}

// run serves until ctx ends, then drains open requests for up to 20 s.
func (a *app) run(ctx context.Context) error {
	if a.cfg.port < 0 || a.cfg.port > 65535 {
		return errors.New("invalid PORT")
	}
	srv := &http.Server{
		Addr:              fmt.Sprintf(":%d", a.cfg.port),
		Handler:           a,
		ReadHeaderTimeout: 10 * time.Second,
		ReadTimeout:       60 * time.Second,
		WriteTimeout:      90 * time.Second, // up to three Roomcord calls of 15 s each
		IdleTimeout:       120 * time.Second,
		MaxHeaderBytes:    16 << 10,
		ErrorLog:          slog.NewLogLogger(a.log.Handler(), slog.LevelWarn),
	}
	a.startSweeper(ctx)
	errc := make(chan error, 1)
	go func() { errc <- srv.ListenAndServe() }()
	a.log.Info(fmt.Sprintf("Tidepath portal on :%d", a.cfg.port), "dryRun", a.cfg.dryRun, "notConfigured", a.notConfigured())
	select {
	case err := <-errc:
		return err
	case <-ctx.Done():
	}
	a.log.Info("shutting down")
	sctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	return srv.Shutdown(sctx)
}

// newLogger writes one JSON object per line: {"t":..., "level":"info", "msg":..., ...}.
// It never logs tokens. Form contents are logged only in PORTAL_DRY_RUN mode.
func newLogger(w io.Writer) *slog.Logger {
	return slog.New(slog.NewJSONHandler(w, &slog.HandlerOptions{
		ReplaceAttr: func(groups []string, a slog.Attr) slog.Attr {
			if len(groups) > 0 {
				return a
			}
			switch a.Key {
			case slog.TimeKey:
				return slog.String("t", a.Value.Time().UTC().Format("2006-01-02T15:04:05.000Z"))
			case slog.LevelKey:
				return slog.String("level", strings.ToLower(a.Value.String()))
			}
			return a
		},
	}))
}

var reDotEnvLine = regexp.MustCompile(`^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$`)

func loadDotEnv(file string) {
	data, err := os.ReadFile(file)
	if err != nil {
		return
	}
	for _, line := range regexp.MustCompile(`\r?\n`).Split(string(data), -1) {
		m := reDotEnvLine.FindStringSubmatch(line)
		if m == nil {
			continue
		}
		if _, set := os.LookupEnv(m[1]); set {
			continue
		}
		v := m[2]
		if len(v) >= 2 && (v[0] == '"' || v[0] == '\'') && v[len(v)-1] == v[0] {
			v = v[1 : len(v)-1]
		}
		os.Setenv(m[1], v)
	}
}

// healthcheck is for the container HEALTHCHECK (distroless has no wget).
func healthcheck() int {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	c := http.Client{Timeout: 3 * time.Second}
	res, err := c.Get("http://127.0.0.1:" + port + "/healthz")
	if err != nil {
		return 1
	}
	res.Body.Close()
	if res.StatusCode != 200 {
		return 1
	}
	return 0
}
