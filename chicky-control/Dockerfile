FROM node:14

# Create app directory
WORKDIR /usr/src/app

# Install app dependencies
COPY package*.json ./
RUN npm install --no-fund --no-package-lock --no-audit

# Bundle app source
COPY . .

EXPOSE 3000
CMD [ "npm", "start" ]