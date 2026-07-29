package main

import (
	"encoding/json"
	"log"
	"sync"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

// Coop is the app's view of the physical coop, kept in sync over MQTT.
//
// The app never talks to the Pi directly. It publishes command topics and
// reads state topics; chicky decides whether a command actually happens. So a
// bug here cannot overfeed the chickens, and the app holding stale state is
// the worst case rather than an unsafe action.

type Climate struct {
	Temperature float64 `json:"temperature"`
	Humidity    float64 `json:"humidity"`
	Pressure    float64 `json:"pressure"`
	Light       float64 `json:"light"`
}

// CoopStatus mirrors chicky's safety-envelope status payload. Field names
// match src/safety.py status().
type CoopStatus struct {
	TreatsAllowed   bool   `json:"treats_allowed"`
	Reason          string `json:"reason"`
	Daylight        bool   `json:"daylight"`
	TreatsToday     int    `json:"treats_today"`
	TreatsRemaining int    `json:"treats_remaining"`
	DailyQuota      int    `json:"daily_quota"`
	CooldownSeconds int    `json:"cooldown_seconds"`
	NextAllowedAt   string `json:"next_allowed_at"`
}

type Coop struct {
	mu sync.RWMutex

	client mqtt.Client
	base   string

	online     bool
	lastSeen   time.Time
	climate    Climate
	climateAt  time.Time
	status     CoopStatus
	statusAt   time.Time
	lightState string
}

func NewCoop(broker, clientID, user, pass, base string) (*Coop, error) {
	c := &Coop{base: base, lightState: "unknown"}

	opts := mqtt.NewClientOptions().
		AddBroker(broker).
		SetClientID(clientID).
		SetUsername(user).
		SetPassword(pass).
		SetAutoReconnect(true).
		SetConnectRetry(true).
		SetConnectRetryInterval(5 * time.Second).
		SetMaxReconnectInterval(60 * time.Second).
		SetKeepAlive(30 * time.Second).
		SetCleanSession(true)

	opts.OnConnect = func(cl mqtt.Client) {
		log.Printf("mqtt connected to %s", broker)
		for _, t := range []string{"availability", "climate", "status", "light/state"} {
			topic := base + "/" + t
			if tok := cl.Subscribe(topic, 1, c.handle); tok.Wait() && tok.Error() != nil {
				log.Printf("mqtt subscribe %s failed: %v", topic, tok.Error())
			}
		}
	}
	opts.OnConnectionLost = func(_ mqtt.Client, err error) {
		log.Printf("mqtt connection lost: %v", err)
		c.mu.Lock()
		c.online = false
		c.mu.Unlock()
	}

	c.client = mqtt.NewClient(opts)
	if tok := c.client.Connect(); tok.Wait() && tok.Error() != nil {
		return nil, tok.Error()
	}
	return c, nil
}

func (c *Coop) handle(_ mqtt.Client, m mqtt.Message) {
	c.mu.Lock()
	defer c.mu.Unlock()
	now := time.Now()
	c.lastSeen = now

	switch m.Topic() {
	case c.base + "/availability":
		c.online = string(m.Payload()) == "online"
	case c.base + "/light/state":
		c.lightState = string(m.Payload())
	case c.base + "/climate":
		var v Climate
		if err := json.Unmarshal(m.Payload(), &v); err != nil {
			log.Printf("bad climate payload: %v", err)
			return
		}
		c.climate, c.climateAt = v, now
	case c.base + "/status":
		var v CoopStatus
		if err := json.Unmarshal(m.Payload(), &v); err != nil {
			log.Printf("bad status payload: %v", err)
			return
		}
		c.status, c.statusAt = v, now
	}
}

// publish sends a command. QoS 1 so a momentary reconnect does not silently
// drop a button press.
func (c *Coop) publish(topic, payload string) error {
	tok := c.client.Publish(c.base+"/"+topic, 1, false, payload)
	tok.WaitTimeout(5 * time.Second)
	return tok.Error()
}

func (c *Coop) Treat() error      { return c.publish("treat/set", "PRESS") }
func (c *Coop) Light(on bool) error {
	if on {
		return c.publish("light/set", "ON")
	}
	return c.publish("light/set", "OFF")
}

type CoopView struct {
	Online      bool       `json:"online"`
	StaleSecs   int        `json:"stale_seconds"`
	Climate     Climate    `json:"climate"`
	Status      CoopStatus `json:"status"`
	LightState  string     `json:"light_state"`
	HasClimate  bool       `json:"has_climate"`
	HasStatus   bool       `json:"has_status"`
}

func (c *Coop) View() CoopView {
	c.mu.RLock()
	defer c.mu.RUnlock()
	v := CoopView{
		Online:     c.online,
		Climate:    c.climate,
		Status:     c.status,
		LightState: c.lightState,
		HasClimate: !c.climateAt.IsZero(),
		HasStatus:  !c.statusAt.IsZero(),
	}
	if !c.lastSeen.IsZero() {
		v.StaleSecs = int(time.Since(c.lastSeen).Seconds())
	} else {
		v.StaleSecs = -1
	}
	return v
}

func (c *Coop) Close() {
	if c.client != nil && c.client.IsConnected() {
		c.client.Disconnect(500)
	}
}
