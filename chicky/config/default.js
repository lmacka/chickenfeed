module.exports = {
  // Server configuration - these are the only required local settings
  port: process.env.PORT || 3000,
  vpsUrl: process.env.REMOTE_SERVER,
  authToken: process.env.AUTH_TOKEN,
  
  // Hardware configuration - these will be provided by the server
  servo1_pin: null,
  servo2_pin: null,
  
  // Operation settings - these will be provided by the server
  debug: false,
  allowed_start_hour: null,
  allowed_end_hour: null,
  timezone_offset: null
};