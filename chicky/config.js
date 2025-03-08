const path = require('path');

module.exports = {
    port: process.env.PORT || 3000,
    debug: process.env.DEBUG === 'true' || false,
    servo1: parseInt(process.env.SERVO1_PIN || '15', 10), // GPIO pin for servo 1
    servo2: parseInt(process.env.SERVO2_PIN || '14', 10), // GPIO pin for servo 2
    vps_url: process.env.VPS_URL || 'https://onlychicks.tv', // VPS URL for Socket.IO
    auth_token: process.env.AUTH_TOKEN || 'default-token-change-me' // Authentication token
};
