# Security Policy

## Reporting

Open a [private security advisory](https://github.com/lmacka/chickenfeed/security/advisories/new)
rather than a public issue. I will confirm receipt and, if it is a real finding, credit you unless
you would rather I did not.

This is a hobby project run by one person, so treat response times accordingly.

## Scope

The deployment at `chook.cam` is in scope. Please do not:

- attempt denial of service, load testing, or anything that hammers the camera or the coop
  hardware
- interact with the physical hardware beyond the normal controls the site offers

There are chickens at the other end of this.

## What is deliberate

A few things look like findings and are not:

- **The control API is unauthenticated by design.** Anyone may take a turn. Access is arbitrated
  by a queue and a Cloudflare Turnstile check, not by accounts.
- **`video.chook.cam` is intentionally not behind the Cloudflare proxy.** Serving video through
  the CDN is barred by Cloudflare's terms on this plan, so the video origin is exposed directly.
- **Encrypted secrets appear in git history.** Historical `.env` files were SOPS-encrypted with
  age; no plaintext credential has ever been committed. Ciphertext in a public repo is expected.

## Design constraints

Physical safety is enforced on the device, not in the web tier. The Raspberry Pi independently
applies a daylight window, a dispense cooldown, a daily quota and a light auto-off timer. A total
compromise of the web application still cannot overfeed the chickens or leave the coop light on
overnight. If you find a way around that, it is a real finding and I would very much like to hear
about it.
