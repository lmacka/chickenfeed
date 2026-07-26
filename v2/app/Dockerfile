FROM golang:1.25-alpine AS build
WORKDIR /src
COPY go.mod go.sum* ./
RUN go mod download || true
COPY *.go ./
RUN go mod tidy && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/chook-app .

FROM gcr.io/distroless/static-debian12:nonroot
WORKDIR /app
COPY --from=build /out/chook-app /app/chook-app
COPY templates/ /app/templates/
COPY static/ /app/static/
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/app/chook-app"]
