package main

import (
	"strings"
	"testing"
)

// A trimmed slice of real mediamtx 1.19 exposition output. The traps it
// encodes: a publisher session that must not count, byte counters sharing
// the webrtc_sessions/hls_sessions name prefix, an SRT publisher, and readers
// of another stream on the same origin (nest, since 2026-09-29).
const metricsFixture = `# HELP paths Number of paths.
# TYPE paths gauge
paths{name="coop",state="ready"} 1
srt_conns{id="f6f7e8f8",path="coop",remoteAddr="1.2.3.4:50594",state="publish"} 1
webrtc_sessions{id="aaa",path="coop",remoteAddr="5.6.7.8:55090",state="read"} 1
webrtc_sessions{id="bbb",path="coop",remoteAddr="9.10.11.12:41000",state="read"} 1
webrtc_sessions{id="ccc",path="coop",remoteAddr="13.14.15.16:42000",state="publish"} 1
webrtc_sessions_outbound_bytes{id="aaa",path="coop",remoteAddr="5.6.7.8:55090",state="read"} 123456
webrtc_sessions{id="ddd",path="nest",remoteAddr="17.18.19.20:43000",state="read"} 1
hls_sessions{id="eee",path="coop",remoteAddr="21.22.23.24:44000"} 1
hls_sessions{id="fff",path="nest",remoteAddr="25.26.27.28:45000"} 1
hls_sessions_outbound_bytes{id="eee",path="coop",remoteAddr="21.22.23.24:44000"} 999999
`

func TestCountReaders(t *testing.T) {
	n, err := countReaders(strings.NewReader(metricsFixture), "coop")
	if err != nil {
		t.Fatalf("countReaders: %v", err)
	}
	// Two WebRTC readers plus one HLS session on coop; the WHIP publisher,
	// the SRT publisher, the byte counters and the nest readers must all be
	// ignored.
	if n != 3 {
		t.Fatalf("got %d readers, want 3", n)
	}
	if n, _ := countReaders(strings.NewReader(metricsFixture), "nest"); n != 2 {
		t.Fatalf("nest: got %d readers, want 2", n)
	}
}

func TestCountReadersPathIsExact(t *testing.T) {
	in := `webrtc_sessions{id="a",path="coop2",state="read"} 1
`
	if n, _ := countReaders(strings.NewReader(in), "coop"); n != 0 {
		t.Fatalf("coop2 counted as coop: got %d", n)
	}
}

func TestCountReadersEmpty(t *testing.T) {
	n, err := countReaders(strings.NewReader("hls_sessions 0\n"), "coop")
	if err != nil || n != 0 {
		t.Fatalf("got %d, %v; want 0, nil", n, err)
	}
}

func TestCountReadersTimestampAndGarbage(t *testing.T) {
	in := `webrtc_sessions{id="a",path="coop",state="read"} 1 1785813152000
not a metric line
webrtc_sessions{id="b",path="coop",state="read"} NaN
`
	n, err := countReaders(strings.NewReader(in), "coop")
	if err != nil {
		t.Fatalf("countReaders: %v", err)
	}
	// The timestamped series counts once; the NaN series is skipped rather
	// than poisoning the sum or erroring out the whole poll.
	if n != 1 {
		t.Fatalf("got %d readers, want 1", n)
	}
}
