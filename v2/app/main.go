// chook-app: the public console for chook.cam.
//
// Runs in-cluster, which is the whole point of the rebuild. The old server sat
// on a public VPS and had to reach INTO the isolated coop VLAN over a Tailscale
// subnet route; when that route stopped being advertised the site went dark for
// months. This process reaches the coop because it is already on the inside,
// and it is exposed to the internet through a Cloudflare Tunnel rather than by
// opening anything.
//
// Deliberately absent, compared to the retired chook-server:
//   - chat. It carried stored XSS on both render paths and a moderation burden.
//   - SSE. The only live data is sensors, health and shared cooldowns, which
//     poll fine. The old page also opened /events twice.
//   - the control queue. Global rate limits are the abuse model now: the
//     hardware has one shared budget and every visitor sees the same
//     countdowns. Turnstile mints a session on the first press instead of
//     guarding a seat.
//
// Video is NOT served here. It comes from video.chook.cam, off the Cloudflare
// proxy, because the CDN terms bar serving video on this plan.
package main

import (
	"encoding/json"
	"errors"
	"html/template"
	"log"
	"net"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

type App struct {
	coop      *Coop
	ptz       *PTZ
	turnstile *Turnstile
	sessions  *Sessions
	viewers   *Viewers
	visitors  *Visitors
	alltime   *PromCount
	brooder   *Brooder
	ptzLimit  *Limiter
	lightLimit *Limiter
	tmpl      *template.Template

	treatMu   sync.Mutex
	treatBusy bool

	videoOrigin  string
	videoPath    string
	turnstileKey string
	presets      []Preset
	trustProxy   bool
	assetVersion string
	treatPreset  string
	treatSettle  time.Duration
}

type Preset struct {
	Token string
	Name  string
	Icon  string
}

var (
	metricCommands = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "chookapp_commands_total", Help: "Commands issued, by kind and outcome.",
	}, []string{"kind", "result"})
	metricCoopOnline = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "chookapp_coop_online", Help: "1 when the coop controller reports online over MQTT.",
	})
	metricSessions = promauto.NewCounter(prometheus.CounterOpts{
		Name: "chookapp_sessions_total", Help: "Turnstile-verified control sessions minted.",
	})
	metricViewers = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "chookapp_viewers", Help: "Live stream readers reported by the video origin (WebRTC + HLS).",
	})
	metricVisitors = promauto.NewCounter(prometheus.CounterOpts{
		Name: "chookapp_visitors_total", Help: "Unique daily page visitors. Counter, so Prometheus owns the history across restarts.",
	})
)

func env(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func envInt(k string, def int) int {
	if v := os.Getenv(k); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
		log.Printf("bad int for %s, using %d", k, def)
	}
	return def
}

func main() {
	log.SetFlags(log.LstdFlags | log.Lmsgprefix)
	log.SetPrefix("chook-app ")

	app := &App{
		turnstile:    NewTurnstile(os.Getenv("TURNSTILE_SECRET")),
		sessions:     NewSessions(time.Duration(envInt("SESSION_TTL_HOURS", 12)) * time.Hour),
		viewers:      NewViewers(os.Getenv("VIDEO_METRICS_URL"), os.Getenv("VIDEO_METRICS_USER"), os.Getenv("VIDEO_METRICS_PASS")),
		visitors:     NewVisitors(env("COOP_TZ", "Australia/Brisbane")),
		// The window is the rf instance's full retention: "all time" means
		// "since counting began", within the 3 years Prometheus keeps.
		alltime: NewPromCount(os.Getenv("VISITORS_PROM_URL"),
			env("VISITORS_PROM_QUERY", "sum(increase(chookapp_visitors_total[1095d]))")),
		ptzLimit:     NewLimiter(time.Duration(envInt("PTZ_COOLDOWN_SECONDS", 5))*time.Second, envInt("PTZ_MOVES_PER_MINUTE", 6)),
		lightLimit:   NewLimiter(time.Duration(envInt("LIGHT_COOLDOWN_SECONDS", 5))*time.Second, 0),
		videoOrigin:  env("VIDEO_ORIGIN", "https://video.chook.cam"),
		videoPath:    env("VIDEO_PATH", "coop"),
		turnstileKey: os.Getenv("TURNSTILE_SITEKEY"),
		trustProxy:   env("TRUST_PROXY", "true") == "true",
		// Cache busting. Cloudflare caches /static/ under its own default TTL
		// (4h for CSS), so without a version in the URL a deploy ships new HTML
		// against stale CSS and the layout silently does not change.
		assetVersion: env("APP_VERSION", strconv.FormatInt(time.Now().Unix(), 10)),
		presets: []Preset{
			{Token: "1", Name: env("PRESET_1_NAME", "Window"), Icon: "1"},
			{Token: "2", Name: env("PRESET_2_NAME", "Feeder"), Icon: "2"},
			{Token: "3", Name: env("PRESET_3_NAME", "Water"), Icon: "3"},
			{Token: "4", Name: env("PRESET_4_NAME", "Bed"), Icon: "4"},
		},
		// A treat only counts if the audience sees it land, so the camera is
		// swung to the feeder preset first and the dispense waits for it.
		// Empty disables the swing.
		treatPreset: env("TREAT_PRESET_TOKEN", "2"),
		treatSettle: time.Duration(envInt("TREAT_SETTLE_SECONDS", 4)) * time.Second,
	}

	if !app.turnstile.Enabled() {
		log.Printf("WARNING: TURNSTILE_SECRET unset, queue entry is unguarded")
	}

	var err error
	app.tmpl, err = template.ParseFiles(env("TEMPLATE_PATH", "templates/index.html"))
	if err != nil {
		log.Fatalf("templates: %v", err)
	}

	app.ptz = NewPTZ(
		env("CAMERA_HOST", "192.168.100.21"),
		env("CAMERA_ONVIF_PORT", "2020"),
		env("CAMERA_PROFILE", "profile_1"),
		env("CAMERA_USER", "tapocam"),
		os.Getenv("CAMERA_PASS"),
		time.Duration(envInt("CAMERA_TIMEOUT_SECONDS", 10))*time.Second,
	)

	// MQTT is required: without it there is no coop state and no way to send a
	// command, so failing fast is better than serving a console that silently
	// does nothing.
	// Client ID must be unique per process. A fixed one makes a rolling update
	// flap: old and new pods share it, the broker evicts whichever connected
	// first, and they fight until the old pod dies. Suffix with the hostname,
	// which is the pod name under Kubernetes.
	clientID := env("MQTT_CLIENT_ID", "chook-app")
	if h, herr := os.Hostname(); herr == nil && h != "" {
		clientID = clientID + "-" + h
	}

	app.coop, err = NewCoop(
		env("MQTT_BROKER", "tcp://mosquitto.homeassist.svc.cluster.local:1883"),
		clientID,
		os.Getenv("MQTT_USER"), os.Getenv("MQTT_PASS"),
		env("MQTT_BASE_TOPIC", "chickenfeed/coop"),
	)
	if err != nil {
		log.Fatalf("mqtt: %v", err)
	}
	defer app.coop.Close()

	go app.metricsLoop()

	if app.viewers.Enabled() {
		go app.viewers.Run(time.Duration(envInt("VIEWERS_POLL_SECONDS", 5)) * time.Second)
	} else {
		log.Printf("viewers: VIDEO_METRICS_URL unset, viewer count disabled")
	}

	if app.alltime.Enabled() {
		go app.alltime.Run(time.Duration(envInt("VISITORS_PROM_POLL_MINUTES", 5)) * time.Minute)
	} else {
		log.Printf("alltime: VISITORS_PROM_URL unset, all-time visitors disabled")
	}

	// The brooder panel: history for the heat-pad Inkbird and the ambient
	// BME280, read back from the rf Prometheus. Off unless enabled, and the
	// page falls back to the plain stats list whenever it is off or broken.
	if env("BROODER_ENABLED", "false") == "true" {
		hatch := time.Unix(int64(envInt("BROODER_HATCH_EPOCH", 0)), 0)
		app.brooder = NewBrooder(
			env("BROODER_PROM_URL", os.Getenv("VISITORS_PROM_URL")),
			env("BROODER_CHANNEL", "ch3"),
			hatch,
		)
		if app.brooder.Enabled() {
			go app.brooder.Run(time.Duration(envInt("BROODER_POLL_SECONDS", 60)) * time.Second)
		} else {
			log.Printf("brooder: no Prometheus URL, panel disabled")
		}
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/", app.handleIndex)
	// Assets are addressed with ?v=<version>, so they can be cached hard and
	// forever: a new build changes the URL rather than waiting out a TTL.
	staticFS := http.StripPrefix("/static/", http.FileServer(http.Dir(env("STATIC_PATH", "static"))))
	mux.Handle("/static/", http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("v") != "" {
			w.Header().Set("Cache-Control", "public, max-age=31536000, immutable")
		} else {
			w.Header().Set("Cache-Control", "public, max-age=300")
		}
		staticFS.ServeHTTP(w, r)
	}))
	mux.HandleFunc("/healthz", app.handleHealth)
	mux.Handle("/metrics", promhttp.Handler())

	mux.HandleFunc("/api/state", app.handleState)
	mux.HandleFunc("/api/brooder", app.brooder.handle)
	mux.HandleFunc("/api/verify", app.handleVerify)
	mux.HandleFunc("/api/treat", app.handleTreat)
	mux.HandleFunc("/api/light", app.handleLight)
	mux.HandleFunc("/api/ptz", app.handlePTZ)

	// Retired endpoints are gone, not merely moved. The queue joined them
	// when global limits replaced it.
	for _, p := range []string{"/events", "/chat/send", "/chat/history", "/api/queue/join", "/api/queue/release"} {
		mux.HandleFunc(p, func(w http.ResponseWriter, _ *http.Request) {
			http.Error(w, "gone", http.StatusGone)
		})
	}

	addr := ":" + env("PORT", "8080")
	srv := &http.Server{
		Addr:              addr,
		Handler:           mux,
		ReadHeaderTimeout: 10 * time.Second,
		ReadTimeout:       20 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       60 * time.Second,
	}
	log.Printf("listening on %s", addr)
	if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatal(err)
	}
}

func (a *App) metricsLoop() {
	for range time.Tick(5 * time.Second) {
		if a.coop.View().Online {
			metricCoopOnline.Set(1)
		} else {
			metricCoopOnline.Set(0)
		}
	}
}

// clientIP prefers the Cloudflare-supplied header, because in production every
// request arrives through the tunnel and RemoteAddr is the tunnel's.
func (a *App) clientIP(r *http.Request) string {
	if a.trustProxy {
		if v := r.Header.Get("CF-Connecting-IP"); v != "" {
			return v
		}
		if v := r.Header.Get("X-Forwarded-For"); v != "" {
			return strings.TrimSpace(strings.Split(v, ",")[0])
		}
	}
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}
	return host
}

func token(r *http.Request) string {
	if v := r.Header.Get("X-Control-Token"); v != "" {
		return v
	}
	return r.FormValue("token")
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

type pageData struct {
	VideoOrigin  string
	VideoPath    string
	TurnstileKey string
	Presets      []Preset
	AssetVersion string
	TreatPreset  string
}

func (a *App) handleIndex(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	// The page must never be cached: it carries the asset version.
	w.Header().Set("Cache-Control", "no-cache")
	a.visitors.Record(a.clientIP(r), time.Now())
	// html/template escapes by default. The retired server built HTML with
	// fmt.Fprintf and shipped stored XSS; this must stay a template.
	if err := a.tmpl.Execute(w, pageData{
		VideoOrigin:  a.videoOrigin,
		VideoPath:    a.videoPath,
		TurnstileKey: a.turnstileKey,
		Presets:      a.presets,
		AssetVersion: a.assetVersion,
		TreatPreset:  a.treatPreset,
	}); err != nil {
		log.Printf("template: %v", err)
	}
}

func (a *App) handleHealth(w http.ResponseWriter, _ *http.Request) {
	v := a.coop.View()
	writeJSON(w, http.StatusOK, map[string]any{
		"status":    "ok",
		"coop":      v.Online,
		"turnstile": a.turnstile.Enabled(),
	})
}

type stateResp struct {
	Coop      CoopView `json:"coop"`
	VideoBase string   `json:"video_base"`
	// Waits are seconds until each control is next allowed, computed here so
	// client clock skew cannot skew the countdowns, and shared so every
	// visitor's page greys and recovers in sync. 0 means go ahead.
	TreatWait int  `json:"treat_wait_seconds"`
	PtzWait   int  `json:"ptz_wait_seconds"`
	LightWait int  `json:"light_wait_seconds"`
	TreatBusy bool `json:"treat_busy"`
	// Viewers is the live reader count from the video origin. null when the
	// origin has not answered recently (or polling is disabled), so the UI
	// hides the indicator rather than showing a number nobody stands behind.
	Viewers *int `json:"viewers"`
	// Unique page visitors this coop-local day: one per client IP, counted
	// in memory, so a deploy starts the day over.
	VisitorsToday int `json:"visitors_today"`
	// All-time uniques, read back from long-retention Prometheus. null when
	// that instance has not answered recently, and the UI hides the row.
	VisitorsAlltime *int `json:"visitors_alltime"`
}

func treatWaitSeconds(v CoopView) int {
	if v.Status.TreatsAllowed || v.Status.NextAllowedAt == "" {
		return 0
	}
	t, err := time.Parse(time.RFC3339, v.Status.NextAllowedAt)
	if err != nil {
		return 0
	}
	d := time.Until(t)
	if d < 0 {
		return 0
	}
	return int(d.Seconds())
}

func (a *App) handleState(w http.ResponseWriter, _ *http.Request) {
	now := time.Now()
	view := a.coop.View()
	a.treatMu.Lock()
	busy := a.treatBusy
	a.treatMu.Unlock()
	var viewers *int
	if n, ok := a.viewers.Current(); ok {
		viewers = &n
	}
	var alltime *int
	if n, ok := a.alltime.Current(); ok {
		alltime = &n
	}
	writeJSON(w, http.StatusOK, stateResp{
		Coop:            view,
		TreatWait:       treatWaitSeconds(view),
		PtzWait:         a.ptzLimit.WaitSeconds(now),
		LightWait:       a.lightLimit.WaitSeconds(now),
		TreatBusy:       busy,
		Viewers:         viewers,
		VisitorsToday:   a.visitors.Today(now),
		VisitorsAlltime: alltime,
		VideoBase:       a.videoOrigin + "/" + a.videoPath,
	})
}

// handleVerify swaps a solved Turnstile challenge for a signed session token.
// This happens once per visitor (per session TTL), on their first press.
func (a *App) handleVerify(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if ok, why := a.turnstile.Verify(r.FormValue("cf-turnstile-response"), a.clientIP(r)); !ok {
		writeJSON(w, http.StatusForbidden, map[string]string{"error": why})
		return
	}
	metricSessions.Inc()
	writeJSON(w, http.StatusOK, map[string]string{"token": a.sessions.Mint(time.Now())})
}

// requireSession is the single gate between a request and the hardware. With
// Turnstile configured, every actuating request must carry a session token
// minted by /api/verify; without it the app runs open (local development).
func (a *App) requireSession(w http.ResponseWriter, r *http.Request) bool {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return false
	}
	if a.turnstile.Enabled() && !a.sessions.Valid(token(r), time.Now()) {
		writeJSON(w, http.StatusForbidden, map[string]string{"error": "verification required"})
		return false
	}
	return true
}

func (a *App) handleTreat(w http.ResponseWriter, r *http.Request) {
	if !a.requireSession(w, r) {
		return
	}
	// Single-flight: one treat sequence at a time, globally. A second press
	// while the camera is swinging would double-dispense or cut the swing.
	a.treatMu.Lock()
	if a.treatBusy {
		a.treatMu.Unlock()
		metricCommands.WithLabelValues("treat", "busy").Inc()
		writeJSON(w, http.StatusConflict, map[string]string{"error": "a treat is already on its way"})
		return
	}
	a.treatBusy = true
	a.treatMu.Unlock()
	defer func() {
		a.treatMu.Lock()
		a.treatBusy = false
		a.treatMu.Unlock()
	}()
	// Report chicky's own refusal reason rather than guessing here. The device
	// is authoritative; this is a courtesy so the UI can say why.
	if v := a.coop.View(); v.HasStatus && !v.Status.TreatsAllowed {
		metricCommands.WithLabelValues("treat", "refused").Inc()
		writeJSON(w, http.StatusConflict, map[string]string{"error": v.Status.Reason})
		return
	}
	// Swing the camera to the feeder before dispensing so the viewer watches
	// the treat land. A PTZ failure logs and dispenses anyway: the chicken
	// getting the treat matters more than the shot. The swing is recorded
	// against the shared PTZ budget so view presses cannot yank the camera
	// away while the treat lands.
	if a.treatPreset != "" {
		a.ptzLimit.Force(time.Now())
		if err := a.ptz.GotoPreset(a.treatPreset); err != nil {
			log.Printf("treat: feeder swing failed: %v", err)
		} else {
			time.Sleep(a.treatSettle)
		}
	}
	if err := a.coop.Treat(); err != nil {
		metricCommands.WithLabelValues("treat", "error").Inc()
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": "could not reach the coop"})
		return
	}
	metricCommands.WithLabelValues("treat", "ok").Inc()
	writeJSON(w, http.StatusOK, map[string]string{"status": "treat requested"})
}

func (a *App) handleLight(w http.ResponseWriter, r *http.Request) {
	if !a.requireSession(w, r) {
		return
	}
	// Only "on" turns it on. This used to be `!= "off"`, so a request with no
	// state parameter at all switched the light ON: the wrong way to fail.
	on := r.FormValue("state") == "on"
	// The UI greys the light at night, but that is CSS. Without this check the
	// coop could be lit at 2am by anyone who posts to this endpoint. chicky's
	// envelope is the authority and enforces a night budget of its own; this
	// is the same refusal made early, and it keeps the API honest about what
	// the interface promises.
	if on {
		if v := a.coop.View(); v.HasStatus && !v.Status.Daylight {
			metricCommands.WithLabelValues("light", "refused").Inc()
			writeJSON(w, http.StatusConflict, map[string]string{"error": "the chickens are asleep, the light is daylight only"})
			return
		}
	}
	if !a.lightLimit.Try(time.Now()) {
		metricCommands.WithLabelValues("light", "limited").Inc()
		writeJSON(w, http.StatusTooManyRequests, map[string]string{"error": "the light needs a moment"})
		return
	}
	if err := a.coop.Light(on); err != nil {
		metricCommands.WithLabelValues("light", "error").Inc()
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": "could not reach the coop"})
		return
	}
	metricCommands.WithLabelValues("light", "ok").Inc()
	writeJSON(w, http.StatusOK, map[string]string{"status": "light toggled"})
}

func (a *App) handlePTZ(w http.ResponseWriter, r *http.Request) {
	if !a.requireSession(w, r) {
		return
	}
	want := r.FormValue("preset")
	// Only the configured preset tokens are accepted, so nothing user-supplied
	// reaches the camera.
	var ok bool
	for _, p := range a.presets {
		if p.Token == want {
			ok = true
			break
		}
	}
	if !ok {
		metricCommands.WithLabelValues("ptz", "invalid").Inc()
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "unknown preset"})
		return
	}
	if !a.ptzLimit.Try(time.Now()) {
		metricCommands.WithLabelValues("ptz", "limited").Inc()
		writeJSON(w, http.StatusTooManyRequests, map[string]string{"error": "the camera needs a moment"})
		return
	}
	if err := a.ptz.GotoPreset(want); err != nil {
		log.Printf("ptz preset %s: %v", want, err)
		metricCommands.WithLabelValues("ptz", "error").Inc()
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": "camera did not move"})
		return
	}
	metricCommands.WithLabelValues("ptz", "ok").Inc()
	writeJSON(w, http.StatusOK, map[string]string{"status": "moving"})
}
