package main

import (
	"bytes"
	"crypto/sha1"
	"encoding/base64"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"time"
)

// CameraController handles direct ONVIF communication with Tapo cameras
type CameraController struct {
	xaddr    string
	username string
	password string
	client   *http.Client
}

// getEnvOrDefaultCamera returns environment variable or default value
func getEnvOrDefaultCamera(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// getEnvAsDurationCamera returns environment variable as duration or default value
func getEnvAsDurationCamera(key string, defaultValue time.Duration) time.Duration {
	if value := os.Getenv(key); value != "" {
		if intVal, err := strconv.Atoi(value); err == nil {
			return time.Duration(intVal) * time.Second
		}
	}
	return defaultValue
}

// NewCameraController creates a new camera controller
func NewCameraController(ip, port, username, password string) *CameraController {
	if port == "" {
		port = getEnvOrDefaultCamera("DEFAULT_ONVIF_PORT", "2020")
	}
	
	return &CameraController{
		xaddr:    fmt.Sprintf("http://%s:%s/onvif/device_service", ip, port),
		username: username,
		password: password,
		client: &http.Client{
			Timeout: getEnvAsDurationCamera("CAMERA_CLIENT_TIMEOUT", 10),
		},
	}
}

// createAuthHeader creates WS-Security authentication header for ONVIF
func (c *CameraController) createAuthHeader() string {
	// Generate nonce and timestamp
	nonce := fmt.Sprintf("%d", time.Now().UnixNano())
	created := time.Now().UTC().Format("2006-01-02T15:04:05.000Z")
	
	// Create password digest
	h := sha1.New()
	h.Write([]byte(nonce + created + c.password))
	passwordDigest := base64.StdEncoding.EncodeToString(h.Sum(nil))
	nonceBase64 := base64.StdEncoding.EncodeToString([]byte(nonce))
	
	return fmt.Sprintf(`
		<Security xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
			<UsernameToken>
				<Username>%s</Username>
				<Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">%s</Password>
				<Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">%s</Nonce>
				<Created xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">%s</Created>
			</UsernameToken>
		</Security>`,
		c.username, passwordDigest, nonceBase64, created)
}

// sendSOAPRequest sends a SOAP request to the camera
func (c *CameraController) sendSOAPRequest(body string) ([]byte, error) {
	authHeader := c.createAuthHeader()
	
	envelope := fmt.Sprintf(`<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
	<s:Header>%s</s:Header>
	<s:Body>%s</s:Body>
</s:Envelope>`, authHeader, body)
	
	req, err := http.NewRequest("POST", c.xaddr, bytes.NewBufferString(envelope))
	if err != nil {
		return nil, err
	}
	
	req.Header.Set("Content-Type", "application/soap+xml; charset=utf-8")
	
	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	return io.ReadAll(resp.Body)
}

// MoveToPreset moves the camera to a preset position
func (c *CameraController) MoveToPreset(presetNumber string) error {
	// Moving camera to preset using direct SOAP
	
	// Try different profile and preset token combinations
	// Based on GetProfiles response, Tapo cameras use profile_1, profile_2, profile_3
	profiles := []string{"profile_1", "profile_2", "Profile_1", "MediaProfile000"}
	presetTokens := []string{presetNumber, "preset" + presetNumber, "Preset" + presetNumber, "preset_" + presetNumber}
	
	for _, profile := range profiles {
		for _, preset := range presetTokens {
			body := fmt.Sprintf(`
				<GotoPreset xmlns="http://www.onvif.org/ver20/ptz/wsdl">
					<ProfileToken>%s</ProfileToken>
					<PresetToken>%s</PresetToken>
				</GotoPreset>`, profile, preset)
			
			resp, err := c.sendSOAPRequest(body)
			if err != nil {
				// Preset combination failed
				continue
			}
			
			// Check if response contains error
			if !bytes.Contains(resp, []byte("Fault")) {
				// Camera moved to preset successfully
				return nil
			}
			
			// SOAP fault occurred
		}
	}
	
	return fmt.Errorf("failed to move to preset %s", presetNumber)
}

// GetProfiles gets the media profiles from the camera
func (c *CameraController) GetProfiles() error {
	body := `<GetProfiles xmlns="http://www.onvif.org/ver10/media/wsdl"/>`
	
	_, err := c.sendSOAPRequest(body)
	if err != nil {
		return fmt.Errorf("failed to get profiles: %v", err)
	}
	
	// GetProfiles response received
	return nil
}

// TestConnection tests the camera connection
func (c *CameraController) TestConnection() error {
	body := `<GetSystemDateAndTime xmlns="http://www.onvif.org/ver10/device/wsdl"/>`
	
	resp, err := c.sendSOAPRequest(body)
	if err != nil {
		return fmt.Errorf("connection test failed: %v", err)
	}
	
	if bytes.Contains(resp, []byte("GetSystemDateAndTimeResponse")) {
		// Camera connection successful
		return nil
	}
	
	return fmt.Errorf("unexpected response from camera")
}