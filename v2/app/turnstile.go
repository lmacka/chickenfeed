package main

import (
	"encoding/json"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// Turnstile guards session minting (/api/verify), not individual button
// presses. One check per visitor per session TTL; the global rate limits
// bound what a verified visitor can do after that.
//
// Server-side siteverify is mandatory: the client token proves nothing on its
// own. Tokens are single-use and expire after 300s.

type Turnstile struct {
	secret string
	client *http.Client
}

func NewTurnstile(secret string) *Turnstile {
	return &Turnstile{secret: secret, client: &http.Client{Timeout: 10 * time.Second}}
}

// Enabled reports whether a secret is configured. With no secret the app runs
// open, which is the right behaviour for local development but must never be
// the case in production.
func (t *Turnstile) Enabled() bool { return t.secret != "" }

type turnstileResp struct {
	Success    bool     `json:"success"`
	ErrorCodes []string `json:"error-codes"`
}

func (t *Turnstile) Verify(token, remoteIP string) (bool, string) {
	if !t.Enabled() {
		return true, "turnstile disabled"
	}
	if strings.TrimSpace(token) == "" {
		return false, "missing token"
	}

	form := url.Values{}
	form.Set("secret", t.secret)
	form.Set("response", token)
	if remoteIP != "" {
		form.Set("remoteip", remoteIP)
	}

	resp, err := t.client.PostForm("https://challenges.cloudflare.com/turnstile/v0/siteverify", form)
	if err != nil {
		// Fail closed: if the check cannot be made, do not hand out a seat.
		return false, "verification unavailable"
	}
	defer resp.Body.Close()

	var out turnstileResp
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return false, "verification unreadable"
	}
	if !out.Success {
		return false, "challenge failed: " + strings.Join(out.ErrorCodes, ",")
	}
	return true, ""
}
