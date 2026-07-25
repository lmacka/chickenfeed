package main

import (
	"bytes"
	"crypto/rand"
	"crypto/sha1"
	"encoding/base64"
	"fmt"
	"io"
	"net/http"
	"time"
)

// Minimal ONVIF PTZ client.
//
// This runs INSIDE the cluster and talks to the camera on the isolated coop
// VLAN. The old design called ONVIF from a public VPS over a Tailscale subnet
// route, which is the dependency that took the site down. The camera is never
// reachable from the internet now.
//
// Values below were read off the live camera rather than guessed:
//   XAddr   http://<ip>:2020/onvif/service   (NOT /onvif/device_service)
//   profile profile_1
//   presets tokens "1".."4", named Viewpoint 1..4
// The previous implementation brute-forced profile and preset token
// combinations because it did not know them. It does now.

type PTZ struct {
	xaddr    string
	profile  string
	username string
	password string
	client   *http.Client
}

func NewPTZ(host, port, profile, user, pass string, timeout time.Duration) *PTZ {
	return &PTZ{
		xaddr:    fmt.Sprintf("http://%s:%s/onvif/service", host, port),
		profile:  profile,
		username: user,
		password: pass,
		client:   &http.Client{Timeout: timeout},
	}
}

// wsSecurity builds a WS-Security UsernameToken with a password digest.
// Digest = Base64(SHA1(nonce + created + password)), per the OASIS profile.
func (p *PTZ) wsSecurity() (string, error) {
	nonce := make([]byte, 16)
	if _, err := rand.Read(nonce); err != nil {
		return "", err
	}
	created := time.Now().UTC().Format("2006-01-02T15:04:05.000Z")

	h := sha1.New()
	h.Write(nonce)
	h.Write([]byte(created))
	h.Write([]byte(p.password))
	digest := base64.StdEncoding.EncodeToString(h.Sum(nil))

	return fmt.Sprintf(`<wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
<wsse:UsernameToken>
<wsse:Username>%s</wsse:Username>
<wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">%s</wsse:Password>
<wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">%s</wsse:Nonce>
<wsu:Created>%s</wsu:Created>
</wsse:UsernameToken>
</wsse:Security>`,
		xmlEscape(p.username), digest,
		base64.StdEncoding.EncodeToString(nonce), created), nil
}

func (p *PTZ) call(body string) ([]byte, error) {
	sec, err := p.wsSecurity()
	if err != nil {
		return nil, err
	}
	env := fmt.Sprintf(`<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
<s:Header>%s</s:Header>
<s:Body>%s</s:Body>
</s:Envelope>`, sec, body)

	req, err := http.NewRequest("POST", p.xaddr, bytes.NewBufferString(env))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/soap+xml; charset=utf-8")

	resp, err := p.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	out, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return nil, err
	}
	// ONVIF reports errors as a SOAP Fault with HTTP 500, so status alone is
	// not enough to tell success from failure.
	if bytes.Contains(out, []byte("Fault")) {
		return out, fmt.Errorf("onvif fault: %s", soapFaultReason(out))
	}
	if resp.StatusCode >= 400 {
		return out, fmt.Errorf("onvif http %d", resp.StatusCode)
	}
	return out, nil
}

// GotoPreset moves the camera to a stored preset token ("1".."4").
func (p *PTZ) GotoPreset(token string) error {
	body := fmt.Sprintf(`<GotoPreset xmlns="http://www.onvif.org/ver20/ptz/wsdl">
<ProfileToken>%s</ProfileToken>
<PresetToken>%s</PresetToken>
</GotoPreset>`, xmlEscape(p.profile), xmlEscape(token))
	_, err := p.call(body)
	return err
}

// Ping is a cheap read-only liveness check used by /healthz.
func (p *PTZ) Ping() error {
	_, err := p.call(`<GetSystemDateAndTime xmlns="http://www.onvif.org/ver10/device/wsdl"/>`)
	return err
}

func soapFaultReason(b []byte) string {
	for _, tag := range []string{"Text", "faultstring"} {
		open := []byte("<" + tag)
		i := bytes.Index(b, open)
		if i < 0 {
			continue
		}
		j := bytes.IndexByte(b[i:], '>')
		if j < 0 {
			continue
		}
		start := i + j + 1
		k := bytes.Index(b[start:], []byte("</"+tag))
		if k < 0 {
			continue
		}
		return string(bytes.TrimSpace(b[start : start+k]))
	}
	return "unknown"
}

func xmlEscape(s string) string {
	var b bytes.Buffer
	for _, r := range s {
		switch r {
		case '&':
			b.WriteString("&amp;")
		case '<':
			b.WriteString("&lt;")
		case '>':
			b.WriteString("&gt;")
		case '"':
			b.WriteString("&quot;")
		case '\'':
			b.WriteString("&apos;")
		default:
			b.WriteRune(r)
		}
	}
	return b.String()
}
