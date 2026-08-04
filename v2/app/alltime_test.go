package main

import (
	"strings"
	"testing"
)

func TestParsePromScalar(t *testing.T) {
	cases := []struct {
		in      string
		want    int
		wantErr bool
	}{
		{`{"status":"success","data":{"resultType":"vector","result":[{"metric":{},"value":[1785800000,"123.7"]}]}}`, 123, false},
		// No history yet: an empty vector is zero, not an error.
		{`{"status":"success","data":{"resultType":"vector","result":[]}}`, 0, false},
		{`{"status":"error","errorType":"bad_data","error":"nope"}`, 0, true},
		{`not json`, 0, true},
	}
	for _, c := range cases {
		got, err := parsePromScalar(strings.NewReader(c.in))
		if (err != nil) != c.wantErr || got != c.want {
			t.Fatalf("parse(%q) = %d, %v; want %d, err=%v", c.in, got, err, c.want, c.wantErr)
		}
	}
}
