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
//   - SSE. With chat gone the only live data is sensors, health and the queue,
//     which polls fine. The old page also opened /events twice.
//   - per-endpoint rate limiting. The control queue does that job structurally.
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
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

type App struct {
	queue     *Queue
	coop      *Coop
	ptz       *PTZ
	turnstile *Turnstile
	tmpl      *template.Template

	videoOrigin  string
	videoPath    string
	turnstileKey string
	presets      []Preset
	trustProxy   bool
	assetVersion string
}

type Preset struct {
	Token string
	Name  string
	Icon  string
}

var (
	metricQueueWaiting = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "chookapp_queue_waiting", Help: "Visitors waiting for the console.",
	})
	metricQueueOccupied = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "chookapp_queue_occupied", Help: "1 when someone holds the console.",
	})
	metricTurns = promauto.NewCounter(prometheus.CounterOpts{
		Name: "chookapp_turns_total", Help: "Control turns handed out.",
	})
	metricCommands = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "chookapp_commands_total", Help: "Commands issued, by kind and outcome.",
	}, []string{"kind", "result"})
	metricCoopOnline = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "chookapp_coop_online", Help: "1 when the coop controller reports online over MQTT.",
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

	turn := time.Duration(envInt("QUEUE_TURN_SECONDS", 30)) * time.Second
	cooldown := time.Duration(envInt("QUEUE_COOLDOWN_SECONDS", 60)) * time.Second
	reap := time.Duration(envInt("QUEUE_REAP_SECONDS", 20)) * time.Second

	app := &App{
		queue:        NewQueue(turn, cooldown, reap),
		turnstile:    NewTurnstile(os.Getenv("TURNSTILE_SECRET")),
		videoOrigin:  env("VIDEO_ORIGIN", "https://video.chook.cam"),
		videoPath:    env("VIDEO_PATH", "coop"),
		turnstileKey: os.Getenv("TURNSTILE_SITEKEY"),
		trustProxy:   env("TRUST_PROXY", "true") == "true",
		// Cache busting. Cloudflare caches /static/ under its own default TTL
		// (4h for CSS), so without a version in the URL a deploy ships new HTML
		// against stale CSS and the layout silently does not change.
		assetVersion: env("APP_VERSION", strconv.FormatInt(time.Now().Unix(), 10)),
		presets: []Preset{
			{Token: "1", Name: env("PRESET_1_NAME", "Viewpoint 1"), Icon: "1"},
			{Token: "2", Name: env("PRESET_2_NAME", "Viewpoint 2"), Icon: "2"},
			{Token: "3", Name: env("PRESET_3_NAME", "Viewpoint 3"), Icon: "3"},
			{Token: "4", Name: env("PRESET_4_NAME", "Viewpoint 4"), Icon: "4"},
		},
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
	mux.HandleFunc("/api/queue/join", app.handleJoin)
	mux.HandleFunc("/api/queue/release", app.handleRelease)
	mux.HandleFunc("/api/treat", app.handleTreat)
	mux.HandleFunc("/api/light", app.handleLight)
	mux.HandleFunc("/api/ptz", app.handlePTZ)

	// The retired chook-server's endpoints are gone, not merely moved.
	for _, p := range []string{"/events", "/chat/send", "/chat/history"} {
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
		s := a.queue.Snapshot()
		metricQueueWaiting.Set(float64(s.Waiting))
		if s.Occupied {
			metricQueueOccupied.Set(1)
		} else {
			metricQueueOccupied.Set(0)
		}
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
	TurnSeconds  int
	AssetVersion string
}

func (a *App) handleIndex(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	// The page must never be cached: it carries the asset version.
	w.Header().Set("Cache-Control", "no-cache")
	// html/template escapes by default. The retired server built HTML with
	// fmt.Fprintf and shipped stored XSS; this must stay a template.
	if err := a.tmpl.Execute(w, pageData{
		VideoOrigin:  a.videoOrigin,
		VideoPath:    a.videoPath,
		TurnstileKey: a.turnstileKey,
		Presets:      a.presets,
		TurnSeconds:  int(a.queue.turn.Seconds()),
		AssetVersion: a.assetVersion,
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
	Queue     QueueSnapshot `json:"queue"`
	Coop      CoopView      `json:"coop"`
	You       youState      `json:"you"`
	VideoBase string        `json:"video_base"`
}

type youState struct {
	Driving     bool `json:"driving"`
	Position    int  `json:"position"`
	SecondsLeft int  `json:"seconds_left"`
	InQueue     bool `json:"in_queue"`
}

func (a *App) handleState(w http.ResponseWriter, r *http.Request) {
	tok := token(r)
	driving, pos, left, _ := a.queue.Status(tok)
	writeJSON(w, http.StatusOK, stateResp{
		Queue: a.queue.Snapshot(),
		Coop:  a.coop.View(),
		You: youState{
			Driving:     driving,
			Position:    pos,
			SecondsLeft: left,
			InQueue:     pos >= 0,
		},
		VideoBase: a.videoOrigin + "/" + a.videoPath,
	})
}

func (a *App) handleJoin(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if ok, why := a.turnstile.Verify(r.FormValue("cf-turnstile-response"), a.clientIP(r)); !ok {
		writeJSON(w, http.StatusForbidden, map[string]string{"error": why})
		return
	}
	if prev := token(r); prev != "" && a.queue.InCooldown(prev) {
		writeJSON(w, http.StatusTooManyRequests, map[string]string{
			"error": "you just had a turn, give someone else a go",
		})
		return
	}

	name := strings.TrimSpace(r.FormValue("name"))
	if name == "" {
		name = "someone"
	}
	if len(name) > 20 {
		name = name[:20]
	}

	res := a.queue.Join(name)
	if res.Driving {
		metricTurns.Inc()
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"token":    res.Token,
		"driving":  res.Driving,
		"position": res.Position,
	})
}

func (a *App) handleRelease(w http.ResponseWriter, r *http.Request) {
	a.queue.Release(token(r))
	writeJSON(w, http.StatusOK, map[string]string{"status": "released"})
}

// requireSeat is the single gate between a request and the hardware.
func (a *App) requireSeat(w http.ResponseWriter, r *http.Request) bool {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return false
	}
	if !a.queue.Holds(token(r)) {
		writeJSON(w, http.StatusForbidden, map[string]string{
			"error": "you do not have the console right now",
		})
		return false
	}
	return true
}

func (a *App) handleTreat(w http.ResponseWriter, r *http.Request) {
	if !a.requireSeat(w, r) {
		return
	}
	// Report chicky's own refusal reason rather than guessing here. The device
	// is authoritative; this is a courtesy so the UI can say why.
	if v := a.coop.View(); v.HasStatus && !v.Status.TreatsAllowed {
		metricCommands.WithLabelValues("treat", "refused").Inc()
		writeJSON(w, http.StatusConflict, map[string]string{"error": v.Status.Reason})
		return
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
	if !a.requireSeat(w, r) {
		return
	}
	on := r.FormValue("state") != "off"
	if err := a.coop.Light(on); err != nil {
		metricCommands.WithLabelValues("light", "error").Inc()
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": "could not reach the coop"})
		return
	}
	metricCommands.WithLabelValues("light", "ok").Inc()
	writeJSON(w, http.StatusOK, map[string]string{"status": "light toggled"})
}

func (a *App) handlePTZ(w http.ResponseWriter, r *http.Request) {
	if !a.requireSeat(w, r) {
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
	if err := a.ptz.GotoPreset(want); err != nil {
		log.Printf("ptz preset %s: %v", want, err)
		metricCommands.WithLabelValues("ptz", "error").Inc()
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": "camera did not move"})
		return
	}
	metricCommands.WithLabelValues("ptz", "ok").Inc()
	writeJSON(w, http.StatusOK, map[string]string{"status": "moving"})
}
