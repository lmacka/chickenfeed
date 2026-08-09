package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"strconv"
	"sync"
	"time"
)

// Brooder feeds the stats-window brooder panel: heat-pad rear/front
// temperatures and humidity from the Inkbird ITH20R on the 433MHz pipeline,
// plus ambient history from chicky's BME280 (coop_climate_*, ingested by
// telegraf). Everything is read from the long-retention rf Prometheus by this
// poller and served from cache; the public page never queries Prometheus.
//
// The sensor is selected by its receiver channel (the label written on the
// unit), not its RF id: the id re-randomises on every battery change and the
// channel does not. The id->channel map lives in telegraf's config, so a
// battery swap touches exactly one place.

const (
	brooderWindow = 12 * time.Hour
	brooderStep   = 10 * time.Minute
	// The Inkbird transmits about once a minute. If its SNR has not changed
	// in this window the radio has gone quiet and every "current" value is a
	// telegraf carry-forward lie.
	brooderStaleWindow = "15m"
)

// brisbane is the coop's clock. Fixed offset: Queensland has no DST.
var brisbane = time.FixedZone("AEST", 10*3600)

type Brooder struct {
	base    string
	channel string
	hatch   time.Time
	client  *http.Client

	mu   sync.RWMutex
	snap *BrooderSnapshot
}

type BrooderSnapshot struct {
	Day     int        `json:"day"`
	Hatched string     `json:"hatched"`
	Start   int64      `json:"start"`
	Step    int        `json:"step"`
	Series  map[string][]*float64 `json:"series"`
	Current map[string]float64    `json:"current"`
	Battery int        `json:"battery"` // percent, -1 unknown
	Alive   bool       `json:"alive"`
	Updated int64      `json:"updated"`
}

func NewBrooder(base, channel string, hatch time.Time) *Brooder {
	return &Brooder{
		base: base, channel: channel, hatch: hatch,
		client: &http.Client{Timeout: 15 * time.Second},
	}
}

func (b *Brooder) Enabled() bool { return b != nil && b.base != "" }

// Run polls forever. Call in a goroutine.
func (b *Brooder) Run(interval time.Duration) {
	for {
		if snap, err := b.fetch(time.Now()); err != nil {
			log.Printf("brooder: %v", err)
		} else {
			b.mu.Lock()
			b.snap = snap
			b.mu.Unlock()
		}
		time.Sleep(interval)
	}
}

func (b *Brooder) handle(w http.ResponseWriter, r *http.Request) {
	if !b.Enabled() {
		http.NotFound(w, r)
		return
	}
	b.mu.RLock()
	snap := b.snap
	b.mu.RUnlock()
	if snap == nil {
		// Not fetched yet (or Prometheus has been down since startup); the
		// page falls back to the plain stats list.
		http.Error(w, "warming up", http.StatusServiceUnavailable)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	json.NewEncoder(w).Encode(snap)
}

func (b *Brooder) fetch(now time.Time) (*BrooderSnapshot, error) {
	end := now.Truncate(brooderStep)
	start := end.Add(-brooderWindow)
	sel := fmt.Sprintf(`{channel=%q}`, b.channel)

	series := map[string][]*float64{}
	current := map[string]float64{}
	ranges := []struct{ name, query string }{
		{"rear", `avg(rtl433_temperature_2_C` + sel + `)`},
		{"front", `avg(rtl433_temperature_C` + sel + `)`},
		{"humidity", `avg(rtl433_humidity` + sel + `)`},
		// Ambient is chicky's BME280 via telegraf; there is only one, so no
		// selector. Missing entirely until that history starts accumulating.
		{"ambient", `avg(coop_climate_temperature)`},
	}
	for _, q := range ranges {
		pts, err := b.queryRange(q.query, start, end)
		if err != nil {
			return nil, fmt.Errorf("%s: %w", q.name, err)
		}
		vals := alignSeries(pts, start.Unix(), int64(brooderStep/time.Second), int(brooderWindow/brooderStep)+1)
		series[q.name] = vals
		if last := lastValue(vals); last != nil && q.name != "ambient" {
			current[q.name] = *last
		}
	}

	battery := -1
	if v, ok, err := b.queryInstant(`avg(rtl433_battery_ok` + sel + `)`); err != nil {
		return nil, fmt.Errorf("battery: %w", err)
	} else if ok {
		battery = int(v*100 + 0.5)
	}
	changes, _, err := b.queryInstant(`sum(changes(rtl433_snr` + sel + `[` + brooderStaleWindow + `]))`)
	if err != nil {
		return nil, fmt.Errorf("alive: %w", err)
	}

	return &BrooderSnapshot{
		Day:     brooderDay(b.hatch, now),
		Hatched: b.hatch.In(brisbane).Format("Mon 2 Jan"),
		Start:   start.Unix(),
		Step:    int(brooderStep / time.Second),
		Series:  series,
		Current: current,
		Battery: battery,
		Alive:   changes > 0,
		Updated: now.Unix(),
	}, nil
}

// brooderDay counts calendar days in Brisbane, day 1 = the hatch date.
func brooderDay(hatch, now time.Time) int {
	h := hatch.In(brisbane)
	n := now.In(brisbane)
	hd := time.Date(h.Year(), h.Month(), h.Day(), 0, 0, 0, 0, brisbane)
	nd := time.Date(n.Year(), n.Month(), n.Day(), 0, 0, 0, 0, brisbane)
	return int(nd.Sub(hd)/(24*time.Hour)) + 1
}

// alignSeries places (ts, value) samples onto the fixed grid, nil where
// Prometheus returned nothing. A gap means the sensor was actually silent
// (past the staleness lookback), which the graph should show as a gap.
func alignSeries(pts []promPoint, start, step int64, n int) []*float64 {
	out := make([]*float64, n)
	for _, p := range pts {
		i := (p.ts - start) / step
		if i >= 0 && i < int64(n) {
			v := p.val
			out[i] = &v
		}
	}
	return out
}

func lastValue(vals []*float64) *float64 {
	for i := len(vals) - 1; i >= 0; i-- {
		if vals[i] != nil {
			return vals[i]
		}
	}
	return nil
}

type promPoint struct {
	ts  int64
	val float64
}

func (b *Brooder) queryRange(query string, start, end time.Time) ([]promPoint, error) {
	u := fmt.Sprintf("%s/api/v1/query_range?query=%s&start=%d&end=%d&step=%d",
		b.base, url.QueryEscape(query), start.Unix(), end.Unix(), int64(brooderStep/time.Second))
	resp, err := b.client.Get(u)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("prometheus: http %d", resp.StatusCode)
	}
	return parsePromMatrix(resp.Body)
}

// queryInstant returns the first sample of an instant query; ok is false when
// the result set is empty (series does not exist yet).
func (b *Brooder) queryInstant(query string) (float64, bool, error) {
	u := b.base + "/api/v1/query?query=" + url.QueryEscape(query)
	resp, err := b.client.Get(u)
	if err != nil {
		return 0, false, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return 0, false, fmt.Errorf("prometheus: http %d", resp.StatusCode)
	}
	var out struct {
		Status string `json:"status"`
		Data   struct {
			Result []struct {
				Value [2]json.RawMessage `json:"value"`
			} `json:"result"`
		} `json:"data"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return 0, false, err
	}
	if out.Status != "success" {
		return 0, false, fmt.Errorf("prometheus: status %q", out.Status)
	}
	if len(out.Data.Result) == 0 {
		return 0, false, nil
	}
	v, err := promValue(out.Data.Result[0].Value[1])
	return v, err == nil, err
}

// parsePromMatrix reads a query_range response and returns the first series'
// samples. An empty result is an empty slice: the series has no history yet.
func parsePromMatrix(r io.Reader) ([]promPoint, error) {
	var out struct {
		Status string `json:"status"`
		Data   struct {
			Result []struct {
				Values [][2]json.RawMessage `json:"values"`
			} `json:"result"`
		} `json:"data"`
	}
	if err := json.NewDecoder(r).Decode(&out); err != nil {
		return nil, err
	}
	if out.Status != "success" {
		return nil, fmt.Errorf("prometheus: status %q", out.Status)
	}
	if len(out.Data.Result) == 0 {
		return nil, nil
	}
	var pts []promPoint
	for _, v := range out.Data.Result[0].Values {
		var ts float64
		if err := json.Unmarshal(v[0], &ts); err != nil {
			return nil, err
		}
		val, err := promValue(v[1])
		if err != nil {
			return nil, err
		}
		pts = append(pts, promPoint{ts: int64(ts), val: val})
	}
	return pts, nil
}

func promValue(raw json.RawMessage) (float64, error) {
	var s string
	if err := json.Unmarshal(raw, &s); err != nil {
		return 0, err
	}
	f, err := strconv.ParseFloat(s, 64)
	if err != nil {
		return 0, fmt.Errorf("prometheus: bad value %q", s)
	}
	return f, nil
}
