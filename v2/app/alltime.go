package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"strconv"
	"sync"
	"time"
)

// PromCount reads the all-time visitor total back from the long-retention
// rf Prometheus, which scrapes chookapp_visitors_total. The app stays
// stateless: it counts, Prometheus remembers, and increase() absorbs the
// counter resetting on every deploy.
//
// Cached and refreshed slowly; the query walks years of samples, so it must
// not run anywhere near the /api/state rate.

type PromCount struct {
	base   string
	query  string
	client *http.Client

	mu    sync.RWMutex
	count int
	at    time.Time
}

const promCountMaxAge = 20 * time.Minute

func NewPromCount(base, query string) *PromCount {
	return &PromCount{base: base, query: query, client: &http.Client{Timeout: 15 * time.Second}}
}

func (p *PromCount) Enabled() bool { return p.base != "" }

// Run polls forever. Call in a goroutine.
func (p *PromCount) Run(interval time.Duration) {
	for {
		if n, err := p.fetch(); err != nil {
			log.Printf("alltime: %v", err)
		} else {
			p.mu.Lock()
			p.count, p.at = n, time.Now()
			p.mu.Unlock()
		}
		time.Sleep(interval)
	}
}

// Current returns the last known total, and false when there is nothing
// fresh enough to show.
func (p *PromCount) Current() (int, bool) {
	p.mu.RLock()
	defer p.mu.RUnlock()
	if p.at.IsZero() || time.Since(p.at) > promCountMaxAge {
		return 0, false
	}
	return p.count, true
}

func (p *PromCount) fetch() (int, error) {
	u := p.base + "/api/v1/query?query=" + url.QueryEscape(p.query)
	resp, err := p.client.Get(u)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return 0, fmt.Errorf("prometheus: http %d", resp.StatusCode)
	}
	return parsePromScalar(resp.Body)
}

// parsePromScalar reads a Prometheus instant-query response and returns the
// first vector sample's value. An empty result is 0: the counter simply has
// no history yet.
func parsePromScalar(r io.Reader) (int, error) {
	var out struct {
		Status string `json:"status"`
		Data   struct {
			Result []struct {
				Value [2]json.RawMessage `json:"value"`
			} `json:"result"`
		} `json:"data"`
	}
	if err := json.NewDecoder(r).Decode(&out); err != nil {
		return 0, fmt.Errorf("prometheus: %w", err)
	}
	if out.Status != "success" {
		return 0, fmt.Errorf("prometheus: status %q", out.Status)
	}
	if len(out.Data.Result) == 0 {
		return 0, nil
	}
	var s string
	if err := json.Unmarshal(out.Data.Result[0].Value[1], &s); err != nil {
		return 0, fmt.Errorf("prometheus: %w", err)
	}
	f, err := strconv.ParseFloat(s, 64)
	if err != nil {
		return 0, fmt.Errorf("prometheus: bad value %q", s)
	}
	return int(f), nil
}
