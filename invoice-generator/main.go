// Command invoicebuilder packages the invoice page as a desktop app.
//
// It serves the embedded page on a fixed local port and opens it in an
// app-style browser window. The fixed port keeps the page's origin stable,
// so invoices saved in localStorage survive restarts. The process exits on
// its own shortly after the last window is closed.
package main

import (
	"bytes"
	"embed"
	"fmt"
	"net"
	"net/http"
	"os"
	"sync"
	"time"
)

//go:embed index.html styles.css app.js
var site embed.FS

const (
	addr = "127.0.0.1:47821"
	url  = "http://" + addr + "/"

	firstPingWait = 2 * time.Minute // time allowed for the window to open
	idleTimeout   = 3 * time.Minute // background tabs may only tick once a minute
	closeGrace    = 8 * time.Second // a reload pings again well within this
)

// heartbeat lets the server notice when every window has been closed.
const heartbeat = `<script>
(function () {
  function ping() { fetch('/ping', { method: 'POST', keepalive: true }).catch(function () {}); }
  ping();
  setInterval(ping, 5000);
  window.addEventListener('pagehide', function () { navigator.sendBeacon('/bye'); });
})();
</script>
</body>`

type tracker struct {
	mu       sync.Mutex
	lastPing time.Time
	closing  time.Time
}

func (t *tracker) ping() {
	t.mu.Lock()
	t.lastPing = time.Now()
	t.closing = time.Time{}
	t.mu.Unlock()
}

func (t *tracker) bye() {
	t.mu.Lock()
	t.closing = time.Now()
	t.mu.Unlock()
}

func (t *tracker) shouldExit(started time.Time) bool {
	t.mu.Lock()
	defer t.mu.Unlock()
	now := time.Now()
	if t.lastPing.IsZero() {
		return now.Sub(started) > firstPingWait
	}
	if !t.closing.IsZero() && now.Sub(t.closing) > closeGrace {
		return true
	}
	return now.Sub(t.lastPing) > idleTimeout
}

func main() {
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		// Already running: just open another window onto it.
		if alreadyRunning() {
			if err := openWindow(url); err != nil {
				fatal(fmt.Sprintf("Could not open a browser window.\n\nOpen %s manually.", url))
			}
			return
		}
		fatal(fmt.Sprintf("Invoice Builder could not start because port %s is in use by another program.\n\n%v", addr[len("127.0.0.1:"):], err))
	}

	index, err := site.ReadFile("index.html")
	if err != nil {
		fatal(err.Error())
	}
	index = bytes.Replace(index, []byte("</body>"), []byte(heartbeat), 1)

	var t tracker
	mux := http.NewServeMux()
	mux.HandleFunc("/ping", func(w http.ResponseWriter, r *http.Request) {
		t.ping()
		w.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("/bye", func(w http.ResponseWriter, r *http.Request) {
		t.bye()
		w.WriteHeader(http.StatusNoContent)
	})
	files := http.FileServerFS(site)
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		if r.URL.Path == "/" || r.URL.Path == "/index.html" {
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			w.Write(index)
			return
		}
		files.ServeHTTP(w, r)
	})

	go http.Serve(ln, mux)

	if err := openWindow(url); err != nil {
		fatal(fmt.Sprintf("Could not open a browser window.\n\nOpen %s manually.", url))
	}

	started := time.Now()
	for range time.Tick(2 * time.Second) {
		if t.shouldExit(started) {
			return
		}
	}
}

func alreadyRunning() bool {
	c := http.Client{Timeout: 2 * time.Second}
	resp, err := c.Post(url+"ping", "text/plain", nil)
	if err != nil {
		return false
	}
	resp.Body.Close()
	return resp.StatusCode == http.StatusNoContent
}

func fatal(msg string) {
	showError(msg)
	os.Exit(1)
}
