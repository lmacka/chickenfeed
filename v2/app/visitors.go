package main

import (
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"log"
	"os"
	"path/filepath"
	"sync"
	"time"
	// Embed the tz database: day-rollover runs in coop time and distroless
	// must not be trusted to carry zoneinfo.
	_ "time/tzdata"
)

// Visitors counts unique page visitors: one per client IP per coop-local
// day, plus a running all-time total. State persists to a small JSON file so
// a pod restart cannot zero the all-time count or double-count a day.
//
// IPs are never stored; the day's dedupe set holds truncated SHA-256 hashes
// and dies with the day.

type Visitors struct {
	mu   sync.Mutex
	path string
	loc  *time.Location

	day      string
	seen     map[string]struct{}
	today    int
	alltime  int
	warnOnce sync.Once
}

type visitorState struct {
	Day     string   `json:"day"`
	Today   int      `json:"today"`
	Alltime int      `json:"alltime"`
	Seen    []string `json:"seen"`
}

func NewVisitors(dir, tz string) *Visitors {
	loc, err := time.LoadLocation(tz)
	if err != nil {
		log.Printf("visitors: bad timezone %q, using UTC: %v", tz, err)
		loc = time.UTC
	}
	v := &Visitors{path: filepath.Join(dir, "visitors.json"), loc: loc, seen: map[string]struct{}{}}
	v.load()
	return v
}

func (v *Visitors) load() {
	b, err := os.ReadFile(v.path)
	if err != nil {
		if !os.IsNotExist(err) {
			log.Printf("visitors: read state: %v", err)
		}
		return
	}
	var s visitorState
	if err := json.Unmarshal(b, &s); err != nil {
		// A corrupt counter must not stop the site; start fresh.
		log.Printf("visitors: corrupt state, starting fresh: %v", err)
		return
	}
	v.day, v.today, v.alltime = s.Day, s.Today, s.Alltime
	for _, h := range s.Seen {
		v.seen[h] = struct{}{}
	}
	log.Printf("visitors: restored %d today (%s), %d all time", v.today, v.day, v.alltime)
}

// save writes atomically. Called with the lock held.
func (v *Visitors) save() {
	s := visitorState{Day: v.day, Today: v.today, Alltime: v.alltime,
		Seen: make([]string, 0, len(v.seen))}
	for h := range v.seen {
		s.Seen = append(s.Seen, h)
	}
	b, _ := json.Marshal(s)
	tmp := v.path + ".tmp"
	if err := os.WriteFile(tmp, b, 0o644); err == nil {
		err = os.Rename(tmp, v.path)
		if err == nil {
			return
		}
	}
	// Unwritable state (no volume in local dev): counting continues
	// in-memory, warned once rather than once per visitor.
	v.warnOnce.Do(func() { log.Printf("visitors: cannot persist to %s", v.path) })
}

func (v *Visitors) roll(now time.Time) {
	day := now.In(v.loc).Format("2006-01-02")
	if v.day == day {
		return
	}
	v.day, v.today = day, 0
	v.seen = map[string]struct{}{}
	v.save()
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
	v.alltime++
	v.save()
}

func (v *Visitors) Snapshot(now time.Time) (today, alltime int) {
	v.mu.Lock()
	defer v.mu.Unlock()
	v.roll(now)
	return v.today, v.alltime
}

func hashIP(ip string) string {
	sum := sha256.Sum256([]byte(ip))
	return base64.RawURLEncoding.EncodeToString(sum[:9])
}
