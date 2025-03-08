FROM node:22-bookworm

# Create a directory for the dependencies that won't be affected by volume mounts
WORKDIR /node_deps

# Copy package.json and package-lock.json for dependency installation
COPY package*.json ./

# Install dependencies using npm ci for deterministic installations based on package-lock.json
RUN npm ci

# Set the working directory for the application (this will be mounted from host)
WORKDIR /usr/src/app

# Set NODE_PATH to include the node_modules directory with our installed dependencies
ENV NODE_PATH=/node_deps/node_modules

# Create directory for certificates
RUN mkdir -p /keys

# Expose the port the app runs on
EXPOSE 3000

# Command to run the application with the NODE_PATH environment variable
CMD ["node", "/usr/src/app/server.js"]