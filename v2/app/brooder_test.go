package main

import (
	"strings"
	"testing"
	"time"
)

func TestAlignSeries(t *testing.T) {
	pts := []promPoint{{ts: 1000, val: 1}, {ts: 1600, val: 2}, {ts: 2800, val: 3}}
	got := alignSeries(pts, 1000, 600, 4)
	if got[0] == nil || *got[0] != 1 {
		t.Fatalf("slot 0: %v", got[0])
	}
	if got[1] == nil || *got[1] != 2 {
		t.Fatalf("slot 1: %v", got[1])
	}
	if got[2] != nil {
		t.Fatalf("slot 2 should be a gap, got %v", *got[2])
	}
	if got[3] == nil || *got[3] != 3 {
		t.Fatalf("slot 3: %v", got[3])
	}
}

func TestAlignSeriesDropsOutOfWindow(t *testing.T) {
	pts := []promPoint{{ts: 400, val: 9}, {ts: 9999, val: 9}}
	got := alignSeries(pts, 1000, 600, 3)
	for i, v := range got {
		if v != nil {
			t.Fatalf("slot %d should be empty, got %v", i, *v)
		}
	}
}

func TestLastValue(t *testing.T) {
	a, b := 1.0, 2.0
	if v := lastValue([]*float64{&a, nil, &b, nil}); v == nil || *v != 2 {
		t.Fatalf("got %v", v)
	}
	if v := lastValue([]*float64{nil, nil}); v != nil {
		t.Fatalf("expected nil, got %v", *v)
	}
}

func TestBrooderDay(t *testing.T) {
	// Hatch: midnight Sat 8 Aug 2026 Brisbane.
	hatch := time.Date(2026, 8, 8, 0, 0, 0, 0, brisbane)
	cases := []struct {
		now time.Time
		day int
	}{
		{time.Date(2026, 8, 8, 0, 1, 0, 0, brisbane), 1},
		{time.Date(2026, 8, 8, 23, 59, 0, 0, brisbane), 1},
		{time.Date(2026, 8, 9, 0, 1, 0, 0, brisbane), 2},
		// 14:05 UTC on the 8th is 00:05 on the 9th in Brisbane: the day must
		// roll on the coop's midnight, not UTC's.
		{time.Date(2026, 8, 8, 14, 5, 0, 0, time.UTC), 2},
		{time.Date(2026, 8, 28, 12, 0, 0, 0, brisbane), 21},
	}
	for _, c := range cases {
		if got := brooderDay(hatch, c.now); got != c.day {
			t.Errorf("day at %s: got %d want %d", c.now, got, c.day)
		}
	}
}

func TestParsePromMatrix(t *testing.T) {
	body := `{"status":"success","data":{"resultType":"matrix","result":[
	  {"metric":{},"values":[[1786216318,"37.5"],[1786216918,"37.6"]]}]}}`
	pts, err := parsePromMatrix(strings.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	if len(pts) != 2 || pts[0].val != 37.5 || pts[1].ts != 1786216918 {
		t.Fatalf("got %+v", pts)
	}
}

func TestParsePromMatrixEmpty(t *testing.T) {
	pts, err := parsePromMatrix(strings.NewReader(`{"status":"success","data":{"result":[]}}`))
	if err != nil || pts != nil {
		t.Fatalf("got %v, %v", pts, err)
	}
}
