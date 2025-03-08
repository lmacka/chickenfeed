FROM balenalib/raspberrypi5-debian-node:20-latest

# Version 1.0.0 - Force rebuild and skip Poetry
# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-smbus \
    i2c-tools && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy package files for Node.js
COPY package*.json ./

# Install Node.js dependencies
RUN npm install --no-fund

# Install Python dependencies directly
RUN pip3 install --no-cache-dir automationhat

# Copy the application code
COPY . .

# Make sure the Python scripts are executable
RUN chmod +x light.py servocontrol.py

# Enable I2C and SPI for hardware access
ENV UDEV=on

# Set up entry point
CMD ["node", "server.js"] 