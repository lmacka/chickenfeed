package main

import (
	"testing"
	"time"
)

func TestLimiterCooldownAndWindow(t *testing.T) {
	l := NewLimiter(5*time.Second, 6)
	t0 := time.Unix(1000, 0)

	if !l.Try(t0) {
		t.Fatal("first move should be allowed")
	}
	if l.Try(t0.Add(2 * time.Second)) {
		t.Fatal("move inside the cooldown should be refused")
	}
	if w := l.WaitSeconds(t0.Add(2 * time.Second)); w < 1 || w > 4 {
		t.Fatalf("cooldown wait = %d, want 1..4", w)
	}

	// Five more moves at 5s spacing exhausts the 6/minute budget.
	now := t0
	for i := 0; i < 5; i++ {
		now = now.Add(5 * time.Second)
		if !l.Try(now) {
			t.Fatalf("move %d within budget should be allowed", i+2)
		}
	}
	now = now.Add(5 * time.Second) // 30s in, cooldown satisfied, window full
	if l.Try(now) {
		t.Fatal("seventh move inside the minute should be refused")
	}
	if w := l.WaitSeconds(now); w < 25 || w > 31 {
		t.Fatalf("window wait = %d, want ~30", w)
	}
	if !l.Try(t0.Add(61 * time.Second)) {
		t.Fatal("move after the window drains should be allowed")
	}
}

func TestLimiterForceCounts(t *testing.T) {
	l := NewLimiter(5*time.Second, 6)
	t0 := time.Unix(1000, 0)
	l.Force(t0)
	if l.Try(t0.Add(1 * time.Second)) {
		t.Fatal("forced move must still start the cooldown")
	}
}

func TestSessions(t *testing.T) {
	s := NewSessions(12 * time.Hour)
	now := time.Unix(1000, 0)
	tok := s.Mint(now)

	if !s.Valid(tok, now.Add(time.Hour)) {
		t.Fatal("fresh token should validate")
	}
	if s.Valid(tok, now.Add(13*time.Hour)) {
		t.Fatal("expired token should fail")
	}
	if s.Valid(tok+"x", now) {
		t.Fatal("tampered token should fail")
	}
	if s.Valid("", now) || s.Valid("a.b", now) {
		t.Fatal("malformed tokens should fail")
	}
	if NewSessions(12*time.Hour).Valid(tok, now) {
		t.Fatal("token from another key should fail")
	}
}
