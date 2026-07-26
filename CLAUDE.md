# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

Interactive chicken coop livestream at [chook.cam](https://chook.cam). Three deployables, each
on a different platform:

| Path | Component | Runs on |
|---|---|---|
| `v2/app/` | `chook-app`: Go, serves the page and the control API | Kubernetes, in-cluster |
| `v2/vps/` | Video relay: mediamtx + swag | Public VPS |
| `v2/chicky/` | Coop controller: servo, relay, I2C sensors | Raspberry Pi 5, balena |

Kubernetes manifests live in a separate private GitOps repo, not here.

## The rule the architecture exists to enforce

**Nothing outside the home reaches in.** Every connection crossing the home boundary is opened
from the inside: the cluster pushes video out over SRT, and the Pi dials out to the MQTT broker.
The previous version had the public VPS reach inward over a VPN subnet route; when that route
stopped being advertised the site died silently for months.

Do not add anything that requires an inbound path to the coop VLAN.

## Non-obvious constraints

- **Browsers only decode Constrained Baseline H.264 over WebRTC.** The camera emits High profile.
  mediamtx does not transcode, so it negotiates `42e01f` and then forwards High profile anyway:
  signalling succeeds and the picture is black. `curl` and `ffprobe` both handle High profile, so
  no command-line check catches it. The pusher must keep `-profile:v baseline`.
- **WebRTC cannot carry AAC.** A WHEP viewer attaching to a stream with an AAC track panics
  mediamtx and exits the process. Publish video-only (`-an`).
- **`MTX_PATHS_*_SRTPUBLISHPASSPHRASE` panics mediamtx.** The passphrase must be set in
  `mediamtx.yml`, which is gitignored, with `mediamtx.yml.example` committed beside it.
- **Defining `authInternalUsers` replaces the mediamtx defaults**, including the localhost-only
  metrics user. Re-add what you still need.
- **The VPS cannot fetch from GitHub** (no deploy key). `git reset --hard origin/main` there walks
  the working tree backwards to a stale ref and deletes the live compose and nginx config. It has
  bitten twice. Push to a temp ref from the workstation and reset onto that.
- **Static assets must carry `?v=$APP_VERSION`.** Cloudflare cached a stylesheet for hours and
  served it long after a fix shipped.

## Safety authority lives on the Pi, not in the app

`v2/chicky/src/safety.py` decides whether a treat is actually dispensed: daylight window from a
real sunrise calculation, cooldown, daily quota persisted to `/data`, light auto-off timer. Both
entry points (HTTP and MQTT) go through it. The web app can only *ask*.

Never move a safety rule into `v2/app/`. The point is that a full compromise of the public site
cannot overfeed the chickens.

## Access control

One visitor holds the console at a time for a 30 second turn, then a 60 second cooldown. Every
actuating endpoint is gated on `queue.Holds(token)`. Turnstile is verified server-side on
`/api/queue/join` only; its tokens are single use, so the widget must be reset after every join.
There is deliberately no per-endpoint rate limiter: the single seat is the limiter.

## Commands

```bash
# console
cd v2/app && go build ./... && go vet ./...
cd v2/app && go run .            # :8080, needs MQTT_* and CAMERA_* or it exits

# coop controller
cd v2/chicky && python main.py   # :3000, mock hardware when GPIO is absent
cd v2/chicky && python test_runner.py
cd v2/chicky && ruff check .
```

CI runs go vet/build/tidy, govulncheck, ruff, the safety tests, and gitleaks. Fix what it finds
rather than suppressing it.

## Conventions

- No secrets in this repository. Config comes from Kubernetes Secrets, balena device variables,
  or a gitignored `.env`.
- The repo is public. Assume anything committed here is read by strangers.
- No em dashes in prose or commit messages.
