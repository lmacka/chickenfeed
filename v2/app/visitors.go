package main

import (
	"crypto/sha256"
	"encoding/base64"
	"log"
	"sync"
	"time"
	// Embed the tz database: day-rollover runs in coop time and distroless
	// must not be trusted to carry zoneinfo.
	_ "time/tzdata"
)

// Visitors counts unique page visitors, one per client IP per coop-local
// day, entirely in memory: the app stays stateless, so a deploy or restart
// starts today's count over. Restarts are rare and the number is a toy, so
// that is the accepted trade against carrying a volume.
//
// Every new unique visitor also increments a monotonic Prometheus counter,
// which is where any durable accounting belongs: Prometheus already owns
// history and handles the counter resetting on restart.
//
// IPs are never stored; the dedupe set holds truncated SHA-256 hashes and
// dies with the day (or the process).

type Visitors struct {
	mu  sync.Mutex
	loc *time.Location

	day   string
	seen  map[string]struct{}
	today int
}

func NewVisitors(tz string) *Visitors {
	loc, err := time.LoadLocation(tz)
	if err != nil {
		log.Printf("visitors: bad timezone %q, using UTC: %v", tz, err)
		loc = time.UTC
	}
	return &Visitors{loc: loc, seen: map[string]struct{}{}}
}

// roll is called with the lock held.
func (v *Visitors) roll(now time.Time) {
	day := now.In(v.loc).Format("2006-01-02")
	if v.day == day {
		return
	}
	v.day, v.today = day, 0
	v.seen = map[string]struct{}{}
}

func (v *Visitors) Record(ip string, now time.Time) {
	h := hashIP(ip)
	v.mu.Lock()
	defer v.mu.Unlock()
	v.roll(now)
	if _, ok := v.seen[h]; ok {
		return
	}
	v.seen[h] = struct{}{}
	v.today++
	metricVisitors.Inc()
}

func (v *Visitors) Today(now time.Time) int {
	v.mu.Lock()
	defer v.mu.Unlock()
	v.roll(now)
	return v.today
}

func hashIP(ip string) string {
	sum := sha256.Sum256([]byte(ip))
	return base64.RawURLEncoding.EncodeToString(sum[:9])
}
