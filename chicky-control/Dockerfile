# Use the official Node.js image as the base image
FROM node:22-bookworm

# Set the working directory
WORKDIR /usr/src/app

# Copy package.json and package-lock.json
COPY package*.json ./

# Install dependencies
RUN npm install

# Verify that node_modules was created and contains express
RUN test -d node_modules && test -d node_modules/express

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 3000

# Command to run the application
CMD ["npm", "start"]