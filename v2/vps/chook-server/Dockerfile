# Build stage
FROM golang:1.21-alpine AS builder

# Install build dependencies for CGO and SQLite
RUN apk add --no-cache gcc musl-dev sqlite-dev

WORKDIR /app

# Install dependencies
COPY go.mod go.sum* ./
RUN go mod download

# Copy source code
COPY . .

# Build the binary with CGO enabled for SQLite
RUN CGO_ENABLED=1 GOOS=linux go build -a -installsuffix cgo -o chook-server .

# Final stage
FROM alpine:latest

# Need sqlite libs at runtime
RUN apk --no-cache add ca-certificates tzdata sqlite-libs

WORKDIR /app

# Copy the binary from builder
COPY --from=builder /app/chook-server .

# Create directories for data, logs, static files and templates
RUN mkdir -p /app/logs /app/data /app/static /app/templates

# Expose port
EXPOSE 3000

# Run the binary
CMD ["./chook-server"]