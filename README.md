# chickenfeed

Live chicken cam at [chook.cam](https://chook.cam): watch the brooder, move
the camera, dispense treats.

[![CI](https://github.com/lmacka/chickenfeed/actions/workflows/ci.yml/badge.svg)](https://github.com/lmacka/chickenfeed/actions/workflows/ci.yml)

## Layout

| Path | What | Runs on |
|---|---|---|
| `v2/app/` | the public console: page and control API (Go) | Kubernetes, in-cluster |
| `v2/vps/` | video relay: mediamtx + swag | small public VPS |
| `v2/chicky/` | coop controller: treat servo, light relay, sensors | Raspberry Pi, balena |

Kubernetes manifests live in a separate private GitOps repo.

The home cluster pushes video out to the relay over SRT; the Pi dials out to
MQTT. Nothing on the internet reaches into the coop. Treat rules (daylight
only, daily quota, cooldown) are enforced on the Pi, so the website can only
ask.

## Running

Config is environment variables; no secrets in this repo.

```bash
cd v2/app && go run .           # console, :8080, needs a reachable MQTT broker
cd v2/chicky && python main.py  # controller, mock hardware without GPIO
cd v2/chicky && python test_runner.py
```

## Licence

GPL-3.0.
