package main

import (
	"testing"
	"time"
)

func TestVisitorsDedupeAndRoll(t *testing.T) {
	v := NewVisitors("Australia/Brisbane")

	day1 := time.Date(2026, 8, 4, 10, 0, 0, 0, time.UTC)
	v.Record("1.2.3.4", day1)
	v.Record("1.2.3.4", day1)
	v.Record("5.6.7.8", day1)
	if got := v.Today(day1); got != 2 {
		t.Fatalf("day1: got %d, want 2", got)
	}

	// Next coop-local day: today resets and yesterday's IPs count again.
	day2 := day1.Add(24 * time.Hour)
	v.Record("1.2.3.4", day2)
	if got := v.Today(day2); got != 1 {
		t.Fatalf("day2: got %d, want 1", got)
	}
}

func TestVisitorsDayBoundaryIsCoopLocal(t *testing.T) {
	v := NewVisitors("Australia/Brisbane")
	// 13:50 and 14:10 UTC straddle midnight in Brisbane (UTC+10).
	before := time.Date(2026, 8, 4, 13, 50, 0, 0, time.UTC)
	after := time.Date(2026, 8, 4, 14, 10, 0, 0, time.UTC)
	v.Record("1.2.3.4", before)
	v.Record("1.2.3.4", after)
	if got := v.Today(after); got != 1 {
		t.Fatalf("got %d, want 1", got)
	}
}
