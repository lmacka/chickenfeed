package main

import (
	"strings"
	"testing"
)

// A trimmed slice of real mediamtx 1.19 exposition output. The traps it
// encodes: a publisher session that must not count, byte counters sharing
// the webrtc_sessions/hls_sessions name prefix, and an SRT publisher.
const metricsFixture = `# HELP paths Number of paths.
# TYPE paths gauge
paths{name="coop",state="ready"} 1
srt_conns{id="f6f7e8f8",path="coop",remoteAddr="1.2.3.4:50594",state="publish"} 1
webrtc_sessions{id="aaa",path="coop",remoteAddr="5.6.7.8:55090",state="read"} 1
webrtc_sessions{id="bbb",path="coop",remoteAddr="9.10.11.12:41000",state="read"} 1
webrtc_sessions{id="ccc",path="coop",remoteAddr="13.14.15.16:42000",state="publish"} 1
webrtc_sessions_outbound_bytes{id="aaa",path="coop",remoteAddr="5.6.7.8:55090",state="read"} 123456
hls_sessions 1
hls_sessions_outbound_bytes 999999
`

func TestCountReaders(t *testing.T) {
	n, err := countReaders(strings.NewReader(metricsFixture))
	if err != nil {
		t.Fatalf("countReaders: %v", err)
	}
	// Two WebRTC readers plus one HLS session; the WHIP publisher, the SRT
	// publisher and the byte counters must all be ignored.
	if n != 3 {
		t.Fatalf("got %d readers, want 3", n)
	}
}

func TestCountReadersEmpty(t *testing.T) {
	n, err := countReaders(strings.NewReader("hls_sessions 0\n"))
	if err != nil || n != 0 {
		t.Fatalf("got %d, %v; want 0, nil", n, err)
	}
}

func TestCountReadersTimestampAndGarbage(t *testing.T) {
	in := `webrtc_sessions{id="a",state="read"} 1 1785813152000
not a metric line
webrtc_sessions{id="b",state="read"} NaN
`
	n, err := countReaders(strings.NewReader(in))
	if err != nil {
		t.Fatalf("countReaders: %v", err)
	}
	// The timestamped series counts once; the NaN series is skipped rather
	// than poisoning the sum or erroring out the whole poll.
	if n != 1 {
		t.Fatalf("got %d readers, want 1", n)
	}
}
