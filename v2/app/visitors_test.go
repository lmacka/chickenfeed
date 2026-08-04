package main

import (
	"testing"
	"time"
)

func TestVisitorsDedupeRollAndPersist(t *testing.T) {
	dir := t.TempDir()
	v := NewVisitors(dir, "Australia/Brisbane")

	day1 := time.Date(2026, 8, 4, 10, 0, 0, 0, time.UTC)
	v.Record("1.2.3.4", day1)
	v.Record("1.2.3.4", day1)
	v.Record("5.6.7.8", day1)
	if today, all := v.Snapshot(day1); today != 2 || all != 2 {
		t.Fatalf("day1: got %d/%d, want 2/2", today, all)
	}

	// Restart mid-day: the same IPs must not count again.
	v2 := NewVisitors(dir, "Australia/Brisbane")
	v2.Record("1.2.3.4", day1)
	if today, all := v2.Snapshot(day1); today != 2 || all != 2 {
		t.Fatalf("after reload: got %d/%d, want 2/2", today, all)
	}

	// Next coop-local day: today resets, all-time keeps counting, and
	// yesterday's IPs are new visitors again.
	day2 := day1.Add(24 * time.Hour)
	v2.Record("1.2.3.4", day2)
	if today, all := v2.Snapshot(day2); today != 1 || all != 3 {
		t.Fatalf("day2: got %d/%d, want 1/3", today, all)
	}
}

func TestVisitorsDayBoundaryIsCoopLocal(t *testing.T) {
	dir := t.TempDir()
	v := NewVisitors(dir, "Australia/Brisbane")
	// 13:50 and 14:10 UTC straddle midnight in Brisbane (UTC+10).
	before := time.Date(2026, 8, 4, 13, 50, 0, 0, time.UTC)
	after := time.Date(2026, 8, 4, 14, 10, 0, 0, time.UTC)
	v.Record("1.2.3.4", before)
	v.Record("1.2.3.4", after)
	if today, all := v.Snapshot(after); today != 1 || all != 2 {
		t.Fatalf("got %d/%d, want 1/2", today, all)
	}
}
