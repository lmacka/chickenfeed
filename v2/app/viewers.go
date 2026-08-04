package main

import (
	"bufio"
	"fmt"
	"io"
	"log"
	"math"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Viewers polls the video origin's Prometheus metrics for the number of live
// stream readers. mediamtx is the only component that knows who is actually
// receiving video (WebRTC and HLS both terminate there), so the count comes
// from it rather than being inferred from page polls here.
//
// The poll runs server-side and the result is cached: clients get the number
// through /api/state, which they already fetch every 2s, so the metrics
// endpoint and its basic-auth credential never face the browser.

type Viewers struct {
	url    string
	user   string
	pass   string
	client *http.Client

	mu    sync.RWMutex
	count int
	at    time.Time
}

// How stale the cached count may be before the UI hides the indicator.
// Serving nothing beats serving a number the origin no longer backs.
const viewersMaxAge = 30 * time.Second

func NewViewers(url, user, pass string) *Viewers {
	return &Viewers{url: url, user: user, pass: pass, client: &http.Client{Timeout: 5 * time.Second}}
}

func (v *Viewers) Enabled() bool { return v.url != "" }

// Run polls forever. Call in a goroutine.
func (v *Viewers) Run(interval time.Duration) {
	for {
		if n, err := v.fetch(); err != nil {
			log.Printf("viewers: %v", err)
		} else {
			v.mu.Lock()
			v.count, v.at = n, time.Now()
			v.mu.Unlock()
			metricViewers.Set(float64(n))
		}
		time.Sleep(interval)
	}
}

// Current returns the last known count, and false when there is nothing
// fresh enough to show.
func (v *Viewers) Current() (int, bool) {
	v.mu.RLock()
	defer v.mu.RUnlock()
	if v.at.IsZero() || time.Since(v.at) > viewersMaxAge {
		return 0, false
	}
	return v.count, true
}

func (v *Viewers) fetch() (int, error) {
	req, err := http.NewRequest(http.MethodGet, v.url, nil)
	if err != nil {
		return 0, err
	}
	if v.user != "" {
		req.SetBasicAuth(v.user, v.pass)
	}
	resp, err := v.client.Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return 0, fmt.Errorf("metrics: http %d", resp.StatusCode)
	}
	return countReaders(io.LimitReader(resp.Body, 4<<20))
}

// countReaders sums the stream-consuming sessions in a Prometheus exposition:
// every webrtc_sessions series in the read state (WHIP publishers report
// state="publish"), plus every hls_sessions series. Names must match exactly;
// webrtc_sessions_* and hls_sessions_* byte counters share the prefix.
func countReaders(r io.Reader) (int, error) {
	total := 0.0
	sc := bufio.NewScanner(r)
	sc.Buffer(make([]byte, 64*1024), 1024*1024)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		name, labels, value, ok := splitSeries(line)
		if !ok {
			continue
		}
		switch name {
		case "webrtc_sessions":
			if !strings.Contains(labels, `state="read"`) {
				continue
			}
		case "hls_sessions":
		default:
			continue
		}
		// ParseFloat accepts "NaN" and "Inf", either of which would poison
		// the whole sum, so only finite values count.
		if n, err := strconv.ParseFloat(value, 64); err == nil && !math.IsNaN(n) && !math.IsInf(n, 0) {
			total += n
		}
	}
	if err := sc.Err(); err != nil {
		return 0, err
	}
	return int(total), nil
}

// splitSeries breaks "name{labels} value [timestamp]" or "name value" into
// its parts.
func splitSeries(line string) (name, labels, value string, ok bool) {
	if i := strings.IndexByte(line, '{'); i >= 0 {
		j := strings.LastIndexByte(line, '}')
		if j < i {
			return "", "", "", false
		}
		name, labels = line[:i], line[i+1:j]
		value = strings.TrimSpace(line[j+1:])
	} else {
		f := strings.Fields(line)
		if len(f) < 2 {
			return "", "", "", false
		}
		name, value = f[0], f[1]
	}
	if f := strings.Fields(value); len(f) > 0 {
		value = f[0]
	}
	return name, labels, value, name != ""
}
