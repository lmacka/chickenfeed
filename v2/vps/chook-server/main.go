package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"html/template"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/joho/godotenv"
	_ "github.com/mattn/go-sqlite3"
	onvifDevice "github.com/use-go/onvif"
	"github.com/use-go/onvif/ptz"
	"github.com/use-go/onvif/xsd/onvif"
)

// getEnvOrDefault returns environment variable or default value
func getEnvOrDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// getEnvAsInt returns environment variable as int or default value
func getEnvAsInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intVal, err := strconv.Atoi(value); err == nil {
			return intVal
		}
	}
	return defaultValue
}

// getEnvAsDuration returns environment variable as duration or default value
func getEnvAsDuration(key string, defaultValue time.Duration) time.Duration {
	if value := os.Getenv(key); value != "" {
		if intVal, err := strconv.Atoi(value); err == nil {
			return time.Duration(intVal) * time.Second
		}
	}
	return defaultValue
}

// Server holds all application state
type Server struct {
	piURL           string
	rateLimiter     map[string]time.Time
	chatRateLimiter map[string][]time.Time
	sseClients      map[string]chan Event
	chatHistory     []ChatMessage
	sensorData      SensorData
	viewerCount     int
	piHealthy       bool
	mu              sync.RWMutex
	templates       *template.Template
	httpClient      *http.Client
	db              *sql.DB
	camera          *onvifDevice.Device
	cameraController *CameraController  // Direct SOAP controller
	cameraMutex     sync.Mutex
}

// Event represents an SSE event
type Event struct {
	Type string      `json:"type"`
	Data interface{} `json:"data"`
}

// ChatMessage represents a chat message
type ChatMessage struct {
	ID        string    `json:"id"`
	Username  string    `json:"username"`
	Message   string    `json:"message"`
	Timestamp time.Time `json:"timestamp"`
	IP        string    `json:"ip,omitempty"`
}

// SensorData represents environmental sensor readings
type SensorData struct {
	Temperature float64   `json:"temperature"`
	Humidity    float64   `json:"humidity"`
	Pressure    float64   `json:"pressure"`
	Light       float64   `json:"light"`
	UpdatedAt   time.Time `json:"updated_at"`
}

// CommandResponse represents API response
type CommandResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
}

// NewServer creates a new server instance
func NewServer() *Server {
	// Load environment variables
	godotenv.Load()

	piURL := os.Getenv("PI_URL")
	if piURL == "" {
		defaultIP := getEnvOrDefault("DEFAULT_TAILSCALE_IP", "100.64.0.1")
		piURL = fmt.Sprintf("http://%s:3000", defaultIP)
	}

	// Get paths from environment
	templatesPath := getEnvOrDefault("TEMPLATES_PATH", "./templates")

	// Parse templates from filesystem
	templates := template.Must(template.ParseGlob(filepath.Join(templatesPath, "*.html")))

	// Get HTTP client timeout from environment
	httpTimeout := getEnvAsDuration("HTTP_CLIENT_TIMEOUT", 5)

	return &Server{
		piURL:       piURL,
		rateLimiter: make(map[string]time.Time),
		sseClients:  make(map[string]chan Event),
		chatHistory: make([]ChatMessage, 0),
		httpClient: &http.Client{
			Timeout: httpTimeout,
		},
		templates: templates,
	}
}

// getClientIP extracts the client IP from the request
func getClientIP(r *http.Request) string {
	// Check common headers for real IP
	if ip := r.Header.Get("X-Real-IP"); ip != "" {
		return ip
	}
	if ip := r.Header.Get("X-Forwarded-For"); ip != "" {
		// Take first IP if multiple
		parts := strings.Split(ip, ",")
		return strings.TrimSpace(parts[0])
	}
	// Fall back to RemoteAddr
	ip := r.RemoteAddr
	// Remove port if present
	if idx := strings.LastIndex(ip, ":"); idx != -1 {
		return ip[:idx]
	}
	return ip
}

// checkRateLimit checks if the client can perform an action
func (s *Server) checkRateLimit(ip string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()

	rateLimitCooldown := getEnvAsDuration("RATE_LIMIT_COOLDOWN_SECONDS", 5)
	lastAction, exists := s.rateLimiter[ip]
	if !exists || time.Since(lastAction) >= rateLimitCooldown {
		s.rateLimiter[ip] = time.Now()
		return true
	}
	return false
}

// handleIndex serves the main page
func (s *Server) handleIndex(w http.ResponseWriter, r *http.Request) {
	// Only serve index for root path
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}

	s.mu.RLock()
	data := struct {
		ViewerCount int
		PiHealthy   bool
		Sensors     SensorData
	}{
		ViewerCount: s.viewerCount,
		PiHealthy:   s.piHealthy,
		Sensors:     s.sensorData,
	}
	s.mu.RUnlock()

	if err := s.templates.ExecuteTemplate(w, "index.html", data); err != nil {
		log.Printf("Error rendering template: %v", err)
		http.Error(w, "Internal server error", http.StatusInternalServerError)
	}
}

// handleStatic serves static files from filesystem
func (s *Server) handleStatic(w http.ResponseWriter, r *http.Request) {
	// Create a file server for the static directory
	staticPath := getEnvOrDefault("STATIC_PATH", "./static")
	fileServer := http.StripPrefix("/static/", http.FileServer(http.Dir(staticPath)))
	fileServer.ServeHTTP(w, r)
}

// handleHealth returns server health status
func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	healthy := s.piHealthy
	s.mu.RUnlock()

	status := map[string]interface{}{
		"server":  "healthy",
		"pi":      healthy,
		"viewers": s.viewerCount,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(status)
}

// broadcastEvent sends an event to all SSE clients
func (s *Server) broadcastEvent(event Event) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	for _, ch := range s.sseClients {
		select {
		case ch <- event:
		default:
			// Client channel is full, skip
		}
	}
}

// startBackgroundTasks starts periodic background tasks
func (s *Server) startBackgroundTasks() {
	// Initialize database
	s.initDatabase()
	
	// Load chat history from database
	s.loadChatHistory()
	
	// Initialize camera connection
	s.initCamera()
	
	// Check Pi health periodically
	healthCheckInterval := getEnvAsDuration("HEALTH_CHECK_INTERVAL", 30)
	go func() {
		ticker := time.NewTicker(healthCheckInterval)
		defer ticker.Stop()

		// Check immediately on startup
		s.checkPiHealth()

		for range ticker.C {
			s.checkPiHealth()
		}
	}()

	// Fetch sensor data periodically
	sensorFetchInterval := getEnvAsDuration("SENSOR_FETCH_INTERVAL", 30)
	go func() {
		ticker := time.NewTicker(sensorFetchInterval)
		defer ticker.Stop()

		// Wait a bit before first fetch
		time.Sleep(2 * time.Second)

		for range ticker.C {
			s.fetchSensorData()
		}
	}()

	// Clean up old rate limit entries periodically
	rateLimitCleanupInterval := getEnvAsDuration("RATE_LIMIT_CLEANUP_INTERVAL", 60)
	rateLimitCleanupMinutes := getEnvAsInt("RATE_LIMIT_CLEANUP_MINUTES", 5)
	go func() {
		ticker := time.NewTicker(rateLimitCleanupInterval)
		defer ticker.Stop()

		for range ticker.C {
			s.mu.Lock()
			now := time.Now()
			for ip, lastTime := range s.rateLimiter {
				if now.Sub(lastTime) > time.Duration(rateLimitCleanupMinutes)*time.Minute {
					delete(s.rateLimiter, ip)
				}
			}
			s.mu.Unlock()
		}
	}()
}

// initDatabase initializes the SQLite database
func (s *Server) initDatabase() {
	dbPath := getEnvOrDefault("DATABASE_PATH", "/app/data/chat.db")
	
	// Ensure data directory exists
	dataDir := filepath.Dir(dbPath)
	if err := os.MkdirAll(dataDir, 0755); err != nil {
		log.Printf("Error creating data directory: %v", err)
		return
	}
	
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		log.Printf("Error opening database: %v", err)
		return
	}
	
	s.db = db
	
	// Create chat table if it doesn't exist
	createTable := `
	CREATE TABLE IF NOT EXISTS chat_messages (
		id TEXT PRIMARY KEY,
		username TEXT NOT NULL,
		message TEXT NOT NULL,
		timestamp INTEGER NOT NULL
	);
	CREATE INDEX IF NOT EXISTS idx_timestamp ON chat_messages(timestamp);
	`
	
	if _, err := db.Exec(createTable); err != nil {
		log.Printf("Error creating chat table: %v", err)
	}
}

// initCamera initializes the ONVIF camera connection
func (s *Server) initCamera() {
	cameraIP := os.Getenv("CAMERA_IP")
	cameraPort := os.Getenv("CAMERA_PORT")
	cameraUser := os.Getenv("CAMERA_USERNAME")
	cameraPass := os.Getenv("CAMERA_PASSWORD")
	
	log.Printf("Camera config - IP: %s, Port: %s, User: %s", cameraIP, cameraPort, cameraUser)
	
	if cameraIP == "" {
		log.Printf("Camera IP not configured")
		return
	}
	
	if cameraPort == "" {
		cameraPort = getEnvOrDefault("DEFAULT_ONVIF_PORT", "2020")
		// Using default ONVIF port
	}
	
	// Try to connect with detailed logging
	xaddr := fmt.Sprintf("http://%s:%s/onvif/device_service", cameraIP, cameraPort)
	// Attempting ONVIF connection
	
	// Try without authentication first to see if the service is there
	deviceNoAuth, errNoAuth := onvifDevice.NewDevice(onvifDevice.DeviceParams{
		Xaddr: xaddr,
	})
	
	if errNoAuth == nil {
		// ONVIF service found, trying with credentials
		// Service exists, now try with auth
		device, err := onvifDevice.NewDevice(onvifDevice.DeviceParams{
			Xaddr:    xaddr,
			Username: cameraUser,
			Password: cameraPass,
		})
		
		if err == nil {
			s.cameraMutex.Lock()
			s.camera = device
			s.cameraMutex.Unlock()
			
			log.Printf("Camera initialized at %s:%s", cameraIP, cameraPort)
			
			// Try to get device information
			go func() {
				deviceInfo := device.GetDeviceInfo()
				if deviceInfo.Manufacturer != "" {
					log.Printf("Camera device info - Manufacturer: %s, Model: %s, Serial: %s",
						deviceInfo.Manufacturer, deviceInfo.Model, deviceInfo.SerialNumber)
				} else {
					log.Printf("Could not get device info")
				}
			}()
			return
		} else {
			log.Printf("ONVIF auth failed: %v", err)
			// Try using the device without auth if it was created
			if deviceNoAuth != nil {
				// Using ONVIF connection without authentication
				s.cameraMutex.Lock()
				s.camera = deviceNoAuth
				s.cameraMutex.Unlock()
				return
			}
		}
	} else {
		log.Printf("ONVIF service check failed: %v", errNoAuth)
		log.Printf("This usually means the ONVIF service is not available or network issue")
	}
	
	// If we're still here, try alternate approaches
	// Trying alternative connection method
	
	// Try with explicit initialization
	device, err := onvifDevice.NewDevice(onvifDevice.DeviceParams{
		Xaddr:    xaddr,
		Username: cameraUser,
		Password: cameraPass,
		HttpClient: &http.Client{
			Timeout: getEnvAsDuration("CAMERA_CLIENT_TIMEOUT", 10),
		},
	})
	
	if err != nil {
		// Extended timeout failed
		log.Printf("ONVIF library failed, will use direct SOAP controller instead")
	} else {
		s.cameraMutex.Lock()
		s.camera = device
		s.cameraMutex.Unlock()
		log.Printf("Camera initialized at %s:%s", cameraIP, cameraPort)
	}
	
	// Always create the direct SOAP controller as fallback/primary for Tapo cameras
	// Creating direct SOAP camera controller
	s.cameraController = NewCameraController(cameraIP, cameraPort, cameraUser, cameraPass)
	
	// Test the connection
	if err := s.cameraController.TestConnection(); err != nil {
		// Direct SOAP connection test failed
	} else {
		log.Printf("Camera connection successful")
		// Try to get profiles to understand the camera better
		s.cameraController.GetProfiles()
	}
}

// fetchSensorData fetches sensor data from the Pi
func (s *Server) fetchSensorData() {
	s.mu.RLock()
	healthy := s.piHealthy
	piURL := s.piURL
	s.mu.RUnlock()

	if !healthy {
		return
	}

	resp, err := s.httpClient.Get(piURL + "/api/sensors")
	if err != nil {
		log.Printf("Background sensor fetch error: %v", err)
		return
	}
	defer resp.Body.Close()

	var sensorResp struct {
		Success     bool    `json:"success"`
		Temperature float64 `json:"temperature"`
		Humidity    float64 `json:"humidity"`
		Pressure    float64 `json:"pressure"`
		Light       float64 `json:"light"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&sensorResp); err != nil {
		log.Printf("Background sensor parse error: %v", err)
		return
	}

	if sensorResp.Success {
		s.mu.Lock()
		s.sensorData = SensorData{
			Temperature: sensorResp.Temperature,
			Humidity:    sensorResp.Humidity,
			Pressure:    sensorResp.Pressure,
			Light:       sensorResp.Light,
			UpdatedAt:   time.Now(),
		}
		s.mu.Unlock()

		// Broadcast updated sensor data
		s.broadcastEvent(Event{
			Type: "sensors",
			Data: s.sensorData,
		})
	}
}

// checkPiHealth checks if the Pi is responsive
func (s *Server) checkPiHealth() {
	resp, err := s.httpClient.Get(s.piURL + "/health")
	
	s.mu.Lock()
	oldHealth := s.piHealthy
	
	if err != nil {
		s.piHealthy = false
		log.Printf("Pi health check error: %v", err)
	} else {
		defer resp.Body.Close()
		if resp.StatusCode != http.StatusOK {
			s.piHealthy = false
			log.Printf("Pi health check failed with status: %d", resp.StatusCode)
		} else {
			s.piHealthy = true
		}
	}
	
	newHealth := s.piHealthy
	s.mu.Unlock()

	// Broadcast health change if status changed
	if oldHealth != newHealth {
		s.broadcastEvent(Event{
			Type: "health",
			Data: map[string]bool{"piHealthy": newHealth},
		})
		log.Printf("Pi health changed: %v -> %v", oldHealth, newHealth)
	}
}

// loadChatHistory loads the last 20 messages from the log file
func (s *Server) loadChatHistory() {
	if s.db == nil {
		log.Printf("Database not initialized")
		return
	}
	
	chatHistorySize := getEnvAsInt("CHAT_HISTORY_SIZE", 50)
	query := fmt.Sprintf(`
	SELECT id, username, message, timestamp 
	FROM chat_messages 
	ORDER BY timestamp DESC 
	LIMIT %d
	`, chatHistorySize)
	
	rows, err := s.db.Query(query)
	if err != nil {
		log.Printf("Error loading chat history: %v", err)
		return
	}
	defer rows.Close()
	
	var messages []ChatMessage
	for rows.Next() {
		var msg ChatMessage
		var timestamp int64
		if err := rows.Scan(&msg.ID, &msg.Username, &msg.Message, &timestamp); err != nil {
			log.Printf("Error scanning chat message: %v", err)
			continue
		}
		msg.Timestamp = time.Unix(0, timestamp)
		messages = append(messages, msg)
	}
	
	// Reverse to get chronological order
	for i := len(messages)/2 - 1; i >= 0; i-- {
		opp := len(messages) - 1 - i
		messages[i], messages[opp] = messages[opp], messages[i]
	}
	
	s.mu.Lock()
	s.chatHistory = messages
	s.mu.Unlock()
	
	log.Printf("Loaded %d chat messages from database", len(messages))
}

// handleCameraPreset handles camera preset commands
func (s *Server) handleCameraPreset(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Extract preset number from URL
	parts := strings.Split(r.URL.Path, "/")
	if len(parts) < 4 {
		w.Header().Set("Content-Type", "text/html")
		fmt.Fprintf(w, `<div class="status-message error">Invalid preset</div>`)
		return
	}
	preset := parts[3]

	// Check rate limit
	ip := getClientIP(r)
	if !s.checkRateLimit(ip) {
		w.Header().Set("Content-Type", "text/html")
		fmt.Fprintf(w, `<div class="status-message error">Rate limited - please wait 5 seconds</div>`)
		return
	}

	// Check Pi health
	s.mu.RLock()
	healthy := s.piHealthy
	s.mu.RUnlock()

	if !healthy {
		w.Header().Set("Content-Type", "text/html")
		fmt.Fprintf(w, `<div class="status-message error">Controller offline</div>`)
		return
	}

	// Map preset numbers to names from environment
	presetNames := map[string]string{
		"1": getEnvOrDefault("CAMERA_PRESET_1_NAME", "Viewpoint 1"),
		"2": getEnvOrDefault("CAMERA_PRESET_2_NAME", "Viewpoint 2"), 
		"3": getEnvOrDefault("CAMERA_PRESET_3_NAME", "Viewpoint 3"),
		"4": getEnvOrDefault("CAMERA_PRESET_4_NAME", "Viewpoint 4"),
	}

	presetName, ok := presetNames[preset]
	if !ok {
		w.Header().Set("Content-Type", "text/html")
		fmt.Fprintf(w, `<div class="status-message error">Invalid preset number</div>`)
		return
	}

	// Check if camera is connected (either ONVIF library or direct SOAP)
	s.cameraMutex.Lock()
	camera := s.camera
	cameraController := s.cameraController
	s.cameraMutex.Unlock()
	
	if camera == nil && cameraController == nil {
		w.Header().Set("Content-Type", "text/html")
		fmt.Fprintf(w, `<div class="status-message error">Camera not connected</div>`)
		return
	}
	
	// Move camera to preset
	go func() {
		if err := s.moveToPreset(preset); err != nil {
			log.Printf("Error moving to preset %s: %v", preset, err)
		} else {
			log.Printf("Camera moved to preset %s", preset)
		}
	}()
	
	// Return success message
	w.Header().Set("Content-Type", "text/html")
	fmt.Fprintf(w, `<div class="status-message">Moving camera to %s</div>`, presetName)
	
	// Broadcast status update
	s.broadcastEvent(Event{
		Type: "status",
		Data: fmt.Sprintf("Camera moving to %s", presetName),
	})
}

// moveToPreset moves the camera to a specific preset
func (s *Server) moveToPreset(presetNumber string) error {
	// Try the direct SOAP controller first (for Tapo cameras)
	if s.cameraController != nil {
		// Using direct SOAP controller for PTZ movement
		err := s.cameraController.MoveToPreset(presetNumber)
		if err == nil {
			return nil
		}
		log.Printf("Direct SOAP failed: %v, trying ONVIF library", err)
	}
	
	// Fall back to ONVIF library if available
	s.cameraMutex.Lock()
	camera := s.camera
	s.cameraMutex.Unlock()
	
	if camera == nil {
		return fmt.Errorf("camera not connected")
	}
	
	// Attempting to move camera to preset
	
	// Try different profile tokens that cameras commonly use
	profileTokens := []string{"Profile_1", "Profile1", "profile_1", "profile1", "Profile_0", "profile_0"}
	presetTokens := []string{
		presetNumber,
		fmt.Sprintf("preset%s", presetNumber),
		fmt.Sprintf("Preset%s", presetNumber),
		fmt.Sprintf("preset_%s", presetNumber),
	}
	
	for _, profileToken := range profileTokens {
		for _, presetToken := range presetTokens {
			// Trying preset combination
			
			res, err := camera.CallMethod(ptz.GotoPreset{
				ProfileToken: onvif.ReferenceToken(profileToken),
				PresetToken:  onvif.ReferenceToken(presetToken),
			})
			
			if err == nil {
				// Camera moved to preset successfully
				_ = res // Response is usually empty for GotoPreset
				return nil
			}
			
			// Preset combination failed
		}
	}
	
	return fmt.Errorf("failed to move to preset %s after trying all combinations", presetNumber)
}

// handleTreat handles treat dispensing
func (s *Server) handleTreat(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Check rate limit
	ip := getClientIP(r)
	if !s.checkRateLimit(ip) {
		w.Header().Set("Content-Type", "text/html")
		fmt.Fprintf(w, `<div class="status-message error">Rate limited - please wait 5 seconds</div>`)
		return
	}

	// Check Pi health
	s.mu.RLock()
	healthy := s.piHealthy
	s.mu.RUnlock()

	if !healthy {
		w.Header().Set("Content-Type", "text/html")
		fmt.Fprintf(w, `<div class="status-message error">Controller offline</div>`)
		return
	}

	// First move camera to TREATS position (preset 4)
	go func() {
		if err := s.moveToPreset("4"); err != nil {
			log.Printf("Error moving camera to treats position: %v", err)
		} else {
			log.Printf("Camera moved to treats position")
		}
	}()

	// Then dispense treat via Pi
	piResp, err := s.httpClient.Post(s.piURL+"/api/treat", "application/json", nil)
	
	if err != nil {
		log.Printf("Error calling Pi treat endpoint: %v", err)
		w.Header().Set("Content-Type", "text/html")
		fmt.Fprintf(w, `<div class="status-message error">Failed to dispense treat</div>`)
		return
	}
	defer piResp.Body.Close()

	// Return HTMX response
	w.Header().Set("Content-Type", "text/html")
	fmt.Fprintf(w, `<div class="status-message">🪱 Treat dispensed! Moving camera to TREATS position</div>`)
	
	// Broadcast status update
	s.broadcastEvent(Event{
		Type: "status",
		Data: "Treat dispensed!",
	})
}

// handleLight handles light toggle
func (s *Server) handleLight(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Check rate limit
	ip := getClientIP(r)
	if !s.checkRateLimit(ip) {
		w.Header().Set("Content-Type", "text/html")
		fmt.Fprintf(w, `<div class="status-message error">Rate limited - please wait 5 seconds</div>`)
		return
	}

	// Check Pi health
	s.mu.RLock()
	healthy := s.piHealthy
	s.mu.RUnlock()

	if !healthy {
		w.Header().Set("Content-Type", "text/html")
		fmt.Fprintf(w, `<div class="status-message error">Controller offline</div>`)
		return
	}

	// Call Pi light endpoint
	piResp, err := s.httpClient.Post(s.piURL+"/api/light", "application/json", nil)
	
	if err != nil {
		log.Printf("Error calling Pi light endpoint: %v", err)
		w.Header().Set("Content-Type", "text/html")
		fmt.Fprintf(w, `<div class="status-message error">Failed to toggle light</div>`)
		return
	}
	defer piResp.Body.Close()

	// Return HTMX response
	w.Header().Set("Content-Type", "text/html")
	fmt.Fprintf(w, `<div class="status-message">💡 Light toggled</div>`)
	
	// Broadcast status update
	s.broadcastEvent(Event{
		Type: "status",
		Data: "Light toggled",
	})
}

// handleSensors returns current sensor readings
func (s *Server) handleSensors(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	healthy := s.piHealthy
	s.mu.RUnlock()

	w.Header().Set("Content-Type", "text/html")
	if !healthy {
		fmt.Fprintf(w, `<div class="sensor-loading">Controller offline</div>`)
		return
	}

	// Fetch sensor data from Pi
	resp, err := s.httpClient.Get(s.piURL + "/api/sensors")
	if err != nil {
		log.Printf("Error fetching sensors: %v", err)
		fmt.Fprintf(w, `<div class="sensor-loading">Sensor error</div>`)
		return
	}
	defer resp.Body.Close()

	// Parse sensor response
	var sensorResp struct {
		Success     bool    `json:"success"`
		Temperature float64 `json:"temperature"`
		Humidity    float64 `json:"humidity"`
		Pressure    float64 `json:"pressure"`
		Light       float64 `json:"light"`
		Error       string  `json:"error,omitempty"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&sensorResp); err != nil {
		log.Printf("Error parsing sensor data: %v", err)
		fmt.Fprintf(w, `<div class="sensor-loading">Sensor data error</div>`)
		return
	}

	if !sensorResp.Success {
		fmt.Fprintf(w, `<div class="sensor-loading">%s</div>`, sensorResp.Error)
		return
	}

	// Update cached sensor data
	s.mu.Lock()
	s.sensorData = SensorData{
		Temperature: sensorResp.Temperature,
		Humidity:    sensorResp.Humidity,
		Pressure:    sensorResp.Pressure,
		Light:       sensorResp.Light,
		UpdatedAt:   time.Now(),
	}
	s.mu.Unlock()

	// Format and return sensor data
	fmt.Fprintf(w, `<div>%.1f°C | %.0fhPa | %.0f%% | %.0flx</div>`,
		sensorResp.Temperature, sensorResp.Pressure, sensorResp.Humidity, sensorResp.Light)
}

// handleSSE handles Server-Sent Events connections
func (s *Server) handleSSE(w http.ResponseWriter, r *http.Request) {
	// Set SSE headers
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	// Create a unique client ID
	clientID := fmt.Sprintf("%d", time.Now().UnixNano())
	clientChan := make(chan Event, 10)

	// Register client
	s.mu.Lock()
	s.sseClients[clientID] = clientChan
	s.viewerCount++
	viewerCount := s.viewerCount
	s.mu.Unlock()

	// Broadcast viewer count update
	s.broadcastEvent(Event{
		Type: "viewers",
		Data: viewerCount,
	})

	// Send initial data to client
	fmt.Fprintf(w, "event: viewers\ndata: %d\n\n", viewerCount)
	
	// Send current health status
	s.mu.RLock()
	healthy := s.piHealthy
	s.mu.RUnlock()
	fmt.Fprintf(w, "event: health\ndata: {\"piHealthy\": %t}\n\n", healthy)

	// Flush immediately
	if f, ok := w.(http.Flusher); ok {
		f.Flush()
	}

	// Clean up on disconnect
	defer func() {
		s.mu.Lock()
		delete(s.sseClients, clientID)
		s.viewerCount--
		viewerCount := s.viewerCount
		s.mu.Unlock()

		close(clientChan)

		// Broadcast updated viewer count
		s.broadcastEvent(Event{
			Type: "viewers",
			Data: viewerCount,
		})
	}()

	// Keep connection alive and send events
	for {
		select {
		case event := <-clientChan:
			// Send event to client
			var data string
			switch v := event.Data.(type) {
			case string:
				data = v
			case int:
				data = fmt.Sprintf("%d", v)
			case bool:
				data = fmt.Sprintf("%t", v)
			default:
				// JSON encode complex data
				jsonData, _ := json.Marshal(v)
				data = string(jsonData)
			}

			fmt.Fprintf(w, "event: %s\ndata: %s\n\n", event.Type, data)
			
			// Flush the data
			if f, ok := w.(http.Flusher); ok {
				f.Flush()
			}

		case <-r.Context().Done():
			// Client disconnected
			return
			
		case <-time.After(getEnvAsDuration("SSE_HEARTBEAT_INTERVAL", 30)):
			// Send heartbeat to keep connection alive
			fmt.Fprintf(w, ": heartbeat\n\n")
			if f, ok := w.(http.Flusher); ok {
				f.Flush()
			}
		}
	}
}

// handleChatSend handles sending chat messages
func (s *Server) handleChatSend(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Parse form data
	r.ParseForm()
	message := strings.TrimSpace(r.FormValue("message"))
	username := strings.TrimSpace(r.FormValue("username"))
	
	if message == "" {
		w.Header().Set("Content-Type", "text/html")
		// Return empty response for HTMX - don't add anything to chat
		return
	}

	// Check rate limit for chat
	chatRateLimitMessages := getEnvAsInt("CHAT_RATE_LIMIT_MESSAGES", 5)
	chatRateLimitWindow := getEnvAsDuration("CHAT_RATE_LIMIT_WINDOW_SECONDS", 10)
	
	ip := getClientIP(r)
	s.mu.Lock()
	
	// Initialize chat rate limiter if needed
	if s.chatRateLimiter == nil {
		s.chatRateLimiter = make(map[string][]time.Time)
	}
	
	// Clean old timestamps
	now := time.Now()
	if timestamps, exists := s.chatRateLimiter[ip]; exists {
		var recent []time.Time
		for _, t := range timestamps {
			if now.Sub(t) < chatRateLimitWindow {
				recent = append(recent, t)
			}
		}
		s.chatRateLimiter[ip] = recent
		
		// Check if rate limited
		if len(recent) >= chatRateLimitMessages {
			s.mu.Unlock()
			w.Header().Set("Content-Type", "text/html")
			// Show error temporarily then clear it
			w.Header().Set("HX-Reswap", "innerHTML")
			w.Header().Set("HX-Retarget", "#chat-error")
			fmt.Fprintf(w, `<div class="chat-error">Rate limited - slow down!</div>`)
			return
		}
	}
	
	// Add current timestamp
	s.chatRateLimiter[ip] = append(s.chatRateLimiter[ip], now)
	
	// Use provided username or generate one
	if username == "" {
		username = fmt.Sprintf("Chook%d", len(s.chatHistory)%1000)
	}
	
	// Sanitize username (max 20 chars, alphanumeric + underscore)
	if len(username) > 20 {
		username = username[:20]
	}
	
	// Create chat message
	chatMsg := ChatMessage{
		ID:        fmt.Sprintf("%d", now.UnixNano()),
		Username:  username,
		Message:   message,
		Timestamp: now,
		IP:        ip,
	}
	
	// Add to history (keep last N messages)
	chatHistorySize := getEnvAsInt("CHAT_HISTORY_SIZE", 50)
	s.chatHistory = append(s.chatHistory, chatMsg)
	if len(s.chatHistory) > chatHistorySize {
		s.chatHistory = s.chatHistory[len(s.chatHistory)-chatHistorySize:]
	}
	s.mu.Unlock()
	
	// Log to file
	s.logChatMessage(chatMsg)
	
	// Broadcast to all clients via SSE
	s.broadcastEvent(Event{
		Type: "chat",
		Data: chatMsg,
	})
	
	// Return empty response - message will appear via SSE
	w.Header().Set("Content-Type", "text/html")
	// Just return empty - the SSE will handle adding the message
}

// logChatMessage saves a chat message to the database
func (s *Server) logChatMessage(msg ChatMessage) {
	if s.db == nil {
		log.Printf("Database not initialized, falling back to file logging")
		s.logChatMessageToFile(msg)
		return
	}
	
	query := `
	INSERT INTO chat_messages (id, username, message, timestamp)
	VALUES (?, ?, ?, ?)
	`
	
	if _, err := s.db.Exec(query, msg.ID, msg.Username, msg.Message, msg.Timestamp.UnixNano()); err != nil {
		log.Printf("Error saving chat message to database: %v", err)
		s.logChatMessageToFile(msg)
	}
}

// logChatMessageToFile logs a chat message to file (fallback)
func (s *Server) logChatMessageToFile(msg ChatMessage) {
	logPath := getEnvOrDefault("LOG_PATH", "/app/logs")
	logFile := filepath.Join(logPath, "chat.json")
	
	// Ensure logs directory exists
	if err := os.MkdirAll(logPath, 0755); err != nil {
		log.Printf("Error creating logs directory: %v", err)
		return
	}
	
	// Create log entry
	logEntry := map[string]interface{}{
		"id":        msg.ID,
		"username":  msg.Username,
		"message":   msg.Message,
		"timestamp": msg.Timestamp.Format(time.RFC3339),
		"ip":        msg.IP,
	}
	
	// Append to file
	file, err := os.OpenFile(logFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		log.Printf("Error opening chat log: %v", err)
		return
	}
	defer file.Close()
	
	encoder := json.NewEncoder(file)
	if err := encoder.Encode(logEntry); err != nil {
		log.Printf("Error writing chat log: %v", err)
	}
}

// handleChatHistory returns recent chat messages
func (s *Server) handleChatHistory(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	messages := make([]ChatMessage, len(s.chatHistory))
	copy(messages, s.chatHistory)
	s.mu.RUnlock()
	
	w.Header().Set("Content-Type", "text/html")
	
	// Return HTML for HTMX
	if len(messages) == 0 {
		fmt.Fprintf(w, `<div class="chat-placeholder">No messages yet. Be the first to chat!</div>`)
		return
	}
	
	for _, msg := range messages {
		fmt.Fprintf(w, `<div class="chat-message">
			<span class="chat-username">%s:</span>
			<span class="chat-text">%s</span>
			<span class="chat-time">%s</span>
		</div>`, msg.Username, msg.Message, msg.Timestamp.Format("15:04"))
	}
}

// setupRoutes configures all HTTP routes
func (s *Server) setupRoutes() {
	http.HandleFunc("/", s.handleIndex)
	http.HandleFunc("/static/", s.handleStatic)
	http.HandleFunc("/health", s.handleHealth)
	
	// API endpoints
	http.HandleFunc("/api/camera/", s.handleCameraPreset)
	http.HandleFunc("/api/treat", s.handleTreat)
	http.HandleFunc("/api/light", s.handleLight)
	http.HandleFunc("/api/sensors", s.handleSensors)
	http.HandleFunc("/events", s.handleSSE)
	http.HandleFunc("/chat/send", s.handleChatSend)
	http.HandleFunc("/chat/history", s.handleChatHistory)
}

func main() {
	server := NewServer()
	
	// Start background tasks
	server.startBackgroundTasks()
	
	// Setup routes
	server.setupRoutes()
	
	// Start server
	port := getEnvOrDefault("PORT", "3000")
	
	log.Printf("Starting Chook Server on port %s", port)
	log.Printf("Pi URL: %s", server.piURL)
	
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatal(err)
	}
}
