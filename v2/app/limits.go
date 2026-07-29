package main

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Global rate limits replaced the control queue as the abuse model. The
// hardware is a shared resource, so the limits are shared too: one visitor's
// press locks the control for everyone, and every client renders the same
// server-computed countdown. Nobody "takes control"; the site is first-come
// within a global budget the hardware is comfortable with.

type Limiter struct {
	mu        sync.Mutex
	cooldown  time.Duration
	perMinute int // 0 disables the sliding-window limit
	last      time.Time
	window    []time.Time
}

func NewLimiter(cooldown time.Duration, perMinute int) *Limiter {
	return &Limiter{cooldown: cooldown, perMinute: perMinute}
}

// Try records the action and reports true if it was within limits.
func (l *Limiter) Try(now time.Time) bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	if l.wait(now) > 0 {
		return false
	}
	l.record(now)
	return true
}

// Force records an action without checking. The treat's feeder swing uses
// this: the treat has priority over view presses, but its camera move still
// counts against the budget so the camera cannot be yanked away mid-treat.
func (l *Limiter) Force(now time.Time) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.record(now)
}

// WaitSeconds is what /api/state serves: seconds until the next action is
// allowed, rounded up so a client never retries a moment early.
func (l *Limiter) WaitSeconds(now time.Time) int {
	l.mu.Lock()
	defer l.mu.Unlock()
	w := l.wait(now)
	if w <= 0 {
		return 0
	}
	return int(w/time.Second) + 1
}

func (l *Limiter) record(now time.Time) {
	l.last = now
	if l.perMinute > 0 {
		l.prune(now)
		l.window = append(l.window, now)
	}
}

func (l *Limiter) prune(now time.Time) {
	cut := now.Add(-time.Minute)
	i := 0
	for i < len(l.window) && l.window[i].Before(cut) {
		i++
	}
	l.window = l.window[i:]
}

func (l *Limiter) wait(now time.Time) time.Duration {
	var w time.Duration
	if !l.last.IsZero() {
		if d := l.cooldown - now.Sub(l.last); d > w {
			w = d
		}
	}
	if l.perMinute > 0 {
		l.prune(now)
		if len(l.window) >= l.perMinute {
			if d := l.window[0].Add(time.Minute).Sub(now); d > w {
				w = d
			}
		}
	}
	return w
}

// Sessions are what Turnstile buys now that the queue is gone. One solved
// challenge mints a signed stateless token; every control press carries it.
// The key is random per process, so a restart quietly re-verifies visitors
// instead of leaking a long-lived secret into config.

type Sessions struct {
	key []byte
	ttl time.Duration
}

func NewSessions(ttl time.Duration) *Sessions {
	k := make([]byte, 32)
	if _, err := rand.Read(k); err != nil {
		panic(err)
	}
	return &Sessions{key: k, ttl: ttl}
}

func (s *Sessions) Mint(now time.Time) string {
	nonce := make([]byte, 8)
	if _, err := rand.Read(nonce); err != nil {
		panic(err)
	}
	payload := strconv.FormatInt(now.Add(s.ttl).Unix(), 10) + "." +
		base64.RawURLEncoding.EncodeToString(nonce)
	return payload + "." + s.sign(payload)
}

func (s *Sessions) Valid(tok string, now time.Time) bool {
	parts := strings.Split(tok, ".")
	if len(parts) != 3 {
		return false
	}
	payload := parts[0] + "." + parts[1]
	if !hmac.Equal([]byte(s.sign(payload)), []byte(parts[2])) {
		return false
	}
	exp, err := strconv.ParseInt(parts[0], 10, 64)
	return err == nil && now.Unix() < exp
}

func (s *Sessions) sign(payload string) string {
	m := hmac.New(sha256.New, s.key)
	m.Write([]byte(payload))
	return base64.RawURLEncoding.EncodeToString(m.Sum(nil))
}
