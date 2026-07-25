package main

import (
	"crypto/rand"
	"encoding/hex"
	"sync"
	"time"
)

// The control queue is the abuse model, not a feature bolted on top of one.
//
// Exactly one visitor holds the console at a time, for a fixed turn. Every
// actuating request must carry that holder's token. Abuse therefore requires
// holding the seat, which is inherently limited to one person, and the cost of
// a bad actor is bounded by the turn length rather than by how fast they can
// send requests. That is why there is no per-endpoint rate limiter here.
//
// Turnstile guards entry to the queue, so the expensive check happens once per
// visitor rather than on every button press.
//
// The device enforces its own limits regardless (daylight, cooldown, daily
// quota). This queue governs *who may ask*; chicky decides *whether it happens*.

type seat struct {
	Token    string
	Name     string
	Expires  time.Time
	Acquired time.Time
}

type waiter struct {
	Token  string
	Name   string
	Joined time.Time
	// seen is refreshed by polling. A visitor who closes the tab stops
	// polling and is reaped, so the queue cannot be blocked by ghosts.
	seen time.Time
}

type Queue struct {
	mu sync.Mutex

	turn     time.Duration
	cooldown time.Duration
	// reapAfter is how long a queued visitor may go without polling before
	// being dropped. Generous relative to the poll interval so a slow phone
	// does not lose its place.
	reapAfter time.Duration

	current  *seat
	waiting  []*waiter
	recent   map[string]time.Time // token -> when its turn ended
	nowFn    func() time.Time     // injectable for tests
	onExpire func()
}

func NewQueue(turn, cooldown, reapAfter time.Duration) *Queue {
	return &Queue{
		turn:      turn,
		cooldown:  cooldown,
		reapAfter: reapAfter,
		recent:    map[string]time.Time{},
		nowFn:     time.Now,
	}
}

func (q *Queue) now() time.Time { return q.nowFn() }

func NewToken() string {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		// crypto/rand failing is not survivable for a token we rely on to
		// gate hardware. Better to refuse than to hand out a guessable seat.
		panic("crypto/rand unavailable: " + err.Error())
	}
	return hex.EncodeToString(b)
}

// tick advances the queue: expires the current turn, reaps absent waiters and
// promotes the next in line. Callers must hold the lock.
func (q *Queue) tick() {
	now := q.now()

	if q.current != nil && now.After(q.current.Expires) {
		q.recent[q.current.Token] = now
		q.current = nil
	}

	// Drop waiters who stopped polling.
	kept := q.waiting[:0]
	for _, w := range q.waiting {
		if now.Sub(w.seen) <= q.reapAfter {
			kept = append(kept, w)
		}
	}
	q.waiting = kept

	if q.current == nil && len(q.waiting) > 0 {
		w := q.waiting[0]
		q.waiting = q.waiting[1:]
		q.current = &seat{
			Token:    w.Token,
			Name:     w.Name,
			Acquired: now,
			Expires:  now.Add(q.turn),
		}
	}

	// Forget cooldowns that have elapsed, so the map cannot grow forever.
	for tok, at := range q.recent {
		if now.Sub(at) > q.cooldown {
			delete(q.recent, tok)
		}
	}
}

type JoinResult struct {
	Token    string
	Position int  // 0 = holds the seat
	Driving  bool
	Rejected string
}

// Join puts a visitor in line, or hands them the seat if it is free.
func (q *Queue) Join(name string) JoinResult {
	q.mu.Lock()
	defer q.mu.Unlock()
	q.tick()

	tok := NewToken()

	if q.current == nil && len(q.waiting) == 0 {
		now := q.now()
		q.current = &seat{Token: tok, Name: name, Acquired: now, Expires: now.Add(q.turn)}
		return JoinResult{Token: tok, Position: 0, Driving: true}
	}

	q.waiting = append(q.waiting, &waiter{Token: tok, Name: name, Joined: q.now(), seen: q.now()})
	return JoinResult{Token: tok, Position: len(q.waiting), Driving: false}
}

// Status refreshes the caller's liveness and reports where they stand.
func (q *Queue) Status(token string) (driving bool, position int, secondsLeft int, waiting int) {
	q.mu.Lock()
	defer q.mu.Unlock()
	q.tick()

	if token != "" {
		for _, w := range q.waiting {
			if w.Token == token {
				w.seen = q.now()
			}
		}
	}

	waiting = len(q.waiting)

	if q.current != nil {
		secondsLeft = int(q.current.Expires.Sub(q.now()).Seconds())
		if secondsLeft < 0 {
			secondsLeft = 0
		}
		if token != "" && q.current.Token == token {
			return true, 0, secondsLeft, waiting
		}
	}

	for i, w := range q.waiting {
		if w.Token == token {
			return false, i + 1, secondsLeft, waiting
		}
	}
	return false, -1, secondsLeft, waiting
}

// Holds reports whether this token currently owns the seat. Every actuating
// handler calls this; it is the single gate between a request and the hardware.
func (q *Queue) Holds(token string) bool {
	if token == "" {
		return false
	}
	q.mu.Lock()
	defer q.mu.Unlock()
	q.tick()
	return q.current != nil && q.current.Token == token
}

// Release gives up the seat early.
func (q *Queue) Release(token string) {
	q.mu.Lock()
	defer q.mu.Unlock()
	q.tick()
	if q.current != nil && q.current.Token == token {
		q.recent[token] = q.now()
		q.current = nil
		q.tick() // promote the next holder immediately
	}
}

// InCooldown reports whether a token just had a turn and may not rejoin yet.
func (q *Queue) InCooldown(token string) bool {
	q.mu.Lock()
	defer q.mu.Unlock()
	at, ok := q.recent[token]
	if !ok {
		return false
	}
	return q.now().Sub(at) < q.cooldown
}

type QueueSnapshot struct {
	Occupied     bool   `json:"occupied"`
	HolderName   string `json:"holder_name,omitempty"`
	SecondsLeft  int    `json:"seconds_left"`
	Waiting      int    `json:"waiting"`
	TurnSeconds  int    `json:"turn_seconds"`
}

func (q *Queue) Snapshot() QueueSnapshot {
	q.mu.Lock()
	defer q.mu.Unlock()
	q.tick()

	s := QueueSnapshot{Waiting: len(q.waiting), TurnSeconds: int(q.turn.Seconds())}
	if q.current != nil {
		s.Occupied = true
		s.HolderName = q.current.Name
		s.SecondsLeft = int(q.current.Expires.Sub(q.now()).Seconds())
		if s.SecondsLeft < 0 {
			s.SecondsLeft = 0
		}
	}
	return s
}
