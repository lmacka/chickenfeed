# TODO

Running list of known work. Add items as they come up, remove them when done.
Anything needing discussion belongs in an issue instead; this is for things we
already know we want.

- [ ] Brooder panel: when this batch leaves the brooder, flip `BROODER_ENABLED`
      off in the GitOps deployment env (otherwise the day counter just keeps
      counting). Next batch: set the new `BROODER_HATCH_EPOCH` there too.
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
- [ ] Fix or delete the ChookVideoOriginRestarted alert: it watches
      process_start_time_seconds{job="chook-video"} but mediamtx exports no
      such metric, so it can never fire (GitOps repo). While there, add a
      stream-staleness alert: the 2026-08-13 pusher hang left the stream dead
      for 20 h with nothing firing.
- [ ] Give stream-pusher's RTSP pull a read timeout (ffmpeg -timeout on the
      input, GitOps repo): a silently dead camera session currently hangs
      ffmpeg forever with the pod Running, instead of exiting into the
      restart loop. Bit us 2026-08-13.
- [ ] Stop serving /metrics through the public tunnel: chook.cam/metrics
      answers to anyone. Only command/session counters leak, but Prometheus
      scrapes in-cluster, so the public route serves nobody. Guard in the
      app (allowlist or separate port) or drop the path at the tunnel
      ingress.
