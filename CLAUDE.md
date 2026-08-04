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
- **`srtPublishPassphrase` does not gate publishing.** It covers the SRT ingest only. WHIP
  (WebRTC publish) is a separate door onto the same path, and mediamtx defaults to
  `overridePublisher`, so granting `action: publish` to `user: any` lets anyone evict the real
  feed and serve their own video. Publish needs its own credentialled entry. Auth is consulted
  for `AuthActionPublish` *before* the passphrase check, so the legitimate publisher depends on
  that entry too.
- **Restarting mediamtx alone 502s the site.** It gets a new docker-bridge IP and nginx has the
  old one cached from startup, so `swag` has to be restarted after it.
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

Global rate limits, shared by all visitors, are the abuse model: PTZ has a 5 second cooldown
plus 6 moves per minute (the treat's feeder swing counts against it), the light a 5 second
cooldown, and treats are single-flight. `/api/state` serves the shared countdowns so every
client greys and recovers in sync. There is no per-visitor seat or queue; `/api/queue/*`
returns 410.

Turnstile mints the control session: the first press calls `/api/verify`, which swaps a
solved challenge for an HMAC-signed 12 hour token that every actuating request must carry.
The signing key is random per process, so a restart silently re-verifies visitors.
Turnstile tokens are single use; the widget must be re-rendered per attempt.

## TODO discipline

`TODO.md` at the repo root is the running work list. When a task, gap, or "later" item
surfaces during any session, add it there in the same commit rather than leaving it in chat
or a commit message. Remove items when done.

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
