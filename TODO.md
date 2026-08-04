# TODO

Running list of known work. Add items as they come up, remove them when done.
Anything needing discussion belongs in an issue instead; this is for things we
already know we want.

- [ ] Confirm camera preset 2 is actually the feeder (needs daylight). If not,
      set `TREAT_PRESET_TOKEN` in the deployment env; no rebuild needed.
- [ ] Tune `TREAT_SETTLE_SECONDS` (default 4) by watching a real treat land
      end to end; stream latency may want a second or two more.
- [ ] Take a fresh browser screenshot of the current UI for the README and
      `v2/app/static/screenshot-lg.png` (the og:image social previews show).
- [ ] Browser-test the interactive Turnstile challenge path (widget replacing
      the spinner in the modal). Needs Cloudflare to actually challenge.
- [ ] Re-test the mediamtx WebRTC/AAC panic on 1.19.3. We publish `-an` so it
      is not gating, but it decides whether coop audio is ever possible.
- [ ] Rotate the camera password and the retired v1 `AUTH_TOKEN` /
      `CHICKY_AUTH_TOKEN` values (ciphertext for them exists in public git
      history).
- [ ] Decide chook-app rollout automation: Flux image automation vs manual
      tag bumps in the GitOps repo.
- [ ] Replace stream-pusher's exec-and-die restart with an in-container retry
      loop: kubelet backoff stretches recovery to minutes after a camera
      outage burst. Design agreed 2026-08-04, not yet shipped (GitOps repo).
- [ ] Fix or delete the ChookVideoOriginRestarted alert: it watches
      process_start_time_seconds{job="chook-video"} but mediamtx exports no
      such metric, so it can never fire (GitOps repo).
