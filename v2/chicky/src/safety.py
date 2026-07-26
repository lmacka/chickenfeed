#!/usr/bin/env python3
"""Device-side safety envelope for the coop hardware.

Every rule here is enforced ON THE PI, deliberately. The public website may
only *ask* for a treat; this module decides whether one is actually dispensed.
That means a bug, or a full compromise, of the web app cannot overfeed the
chickens or leave the coop light burning all night.

Both entry points (the HTTP API and the MQTT bridge) go through this, so there
is no path that bypasses it.

Failure behaviour is chosen per-rule:
  - If the sun calculation fails, fall back to a fixed local-time window rather
    than denying outright. A broken almanac should not brick the feeder.
  - If the state file is unreadable, start from zero rather than crash. Losing
    a day's quota count is preferable to the controller not starting.
"""

import json
import logging
import os
import threading
from datetime import datetime
from datetime import time as dtime

logger = logging.getLogger(__name__)

STATE_DIR = os.getenv("STATE_DIR", "/data")
STATE_FILE = os.path.join(STATE_DIR, "safety_state.json")

# Fallback daylight window, used only if the sun calculation is unavailable.
FALLBACK_DAWN = dtime(6, 0)
FALLBACK_DUSK = dtime(18, 0)


def _env_float(name, default):
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        logger.warning("Bad value for %s, using default %s", name, default)
        return float(default)


def _env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        logger.warning("Bad value for %s, using default %s", name, default)
        return int(default)


class SafetyEnvelope:
    """Authoritative gate on every physical action the coop can take."""

    def __init__(self, relay=None):
        self.relay = relay
        self._lock = threading.RLock()

        self.timezone = os.getenv("COOP_TZ", "Australia/Brisbane")
        self.latitude = _env_float("COOP_LAT", -27.47)
        self.longitude = _env_float("COOP_LON", 153.03)

        # Minimum gap between dispenses. The servo driver already enforces 5s
        # as a mechanical guard; this is the higher, policy-level limit that
        # stops a public button turning into a feed firehose.
        self.treat_cooldown = _env_int("TREAT_COOLDOWN_SECONDS", 30)
        self.treat_daily_quota = _env_int("TREAT_DAILY_QUOTA", 20)
        self.light_auto_off_minutes = _env_int("LIGHT_AUTO_OFF_MINUTES", 30)
        self.daylight_only = os.getenv("TREAT_DAYLIGHT_ONLY", "true").lower() != "false"

        self._last_dispense = None
        self._dispense_count = 0
        self._quota_day = None
        self._dispensing = False
        self._light_timer = None
        self._light_on_since = None

        self._load()

    # ---------- persistence ----------

    def _load(self):
        try:
            with open(STATE_FILE, encoding="utf-8") as fh:
                data = json.load(fh)
            self._quota_day = data.get("quota_day")
            self._dispense_count = int(data.get("dispense_count", 0))
            last = data.get("last_dispense")
            self._last_dispense = datetime.fromisoformat(last) if last else None
            logger.info(
                "Safety state loaded: %s dispenses on %s",
                self._dispense_count, self._quota_day,
            )
        except FileNotFoundError:
            logger.info("No safety state file yet, starting fresh")
        except Exception as exc:
            # Deliberately non-fatal: a corrupt counter must not stop the coop.
            logger.error("Could not read safety state (%s); starting fresh", exc)

    def _save(self):
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            tmp = STATE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({
                    "quota_day": self._quota_day,
                    "dispense_count": self._dispense_count,
                    "last_dispense": self._last_dispense.isoformat() if self._last_dispense else None,
                }, fh)
            os.replace(tmp, STATE_FILE)
        except Exception as exc:
            logger.error("Could not persist safety state: %s", exc)

    # ---------- time / daylight ----------

    def _now(self):
        try:
            from zoneinfo import ZoneInfo
            return datetime.now(ZoneInfo(self.timezone))
        except Exception:
            return datetime.now()

    def is_daylight(self):
        """True when the sun is up at the coop.

        Uses a real sunrise/sunset calculation when astral is available, and a
        fixed local-time window otherwise. The point of the rule is the
        chickens' sleep schedule, so it keys off the sun rather than measured
        lux: switching the coop light on at midnight must not unlock treats.
        """
        now = self._now()
        try:
            from astral import LocationInfo
            from astral.sun import sun
            loc = LocationInfo(
                name="coop", region="AU", timezone=self.timezone,
                latitude=self.latitude, longitude=self.longitude,
            )
            times = sun(loc.observer, date=now.date(), tzinfo=now.tzinfo)
            return times["sunrise"] <= now <= times["sunset"]
        except Exception as exc:
            logger.warning("Sun calculation unavailable (%s); using fixed window", exc)
            return FALLBACK_DAWN <= now.time() <= FALLBACK_DUSK

    def _roll_quota_if_needed(self, now):
        today = now.date().isoformat()
        if self._quota_day != today:
            self._quota_day = today
            self._dispense_count = 0
            self._save()

    # ---------- treat ----------

    def can_dispense(self):
        """Return (allowed, reason). Reason is written for a human to read."""
        with self._lock:
            now = self._now()
            self._roll_quota_if_needed(now)

            if self._dispensing:
                return False, "a dispense is already in progress"

            if self.daylight_only and not self.is_daylight():
                return False, "the chickens are asleep, treats are daylight only"

            if self._dispense_count >= self.treat_daily_quota:
                return False, f"daily treat limit of {self.treat_daily_quota} reached"

            if self._last_dispense is not None:
                elapsed = (now - self._last_dispense).total_seconds()
                if elapsed < self.treat_cooldown:
                    wait = int(self.treat_cooldown - elapsed) + 1
                    return False, f"cooling down, try again in {wait}s"

            return True, "ok"

    def begin_dispense(self):
        """Claim the dispenser. Returns (allowed, reason)."""
        with self._lock:
            allowed, reason = self.can_dispense()
            if allowed:
                self._dispensing = True
            return allowed, reason

    def end_dispense(self, success):
        with self._lock:
            self._dispensing = False
            if success:
                self._last_dispense = self._now()
                self._dispense_count += 1
                self._save()

    # ---------- light ----------

    def note_light_on(self):
        """Start (or restart) the auto-off timer so the light cannot stay on.

        Chickens need real darkness. Any path that turns the light on goes
        through here, so a forgotten toggle or a wedged web app still ends with
        the light off.
        """
        with self._lock:
            self._cancel_light_timer()
            self._light_on_since = self._now()
            if self.light_auto_off_minutes <= 0:
                return
            self._light_timer = threading.Timer(
                self.light_auto_off_minutes * 60, self._auto_off
            )
            self._light_timer.daemon = True
            self._light_timer.start()
            logger.info("Coop light on; auto-off in %s min", self.light_auto_off_minutes)

    def note_light_off(self):
        with self._lock:
            self._cancel_light_timer()
            self._light_on_since = None

    def _cancel_light_timer(self):
        if self._light_timer is not None:
            self._light_timer.cancel()
            self._light_timer = None

    def _auto_off(self):
        logger.warning("Coop light auto-off timer fired; turning the light off")
        try:
            if self.relay is not None:
                self.relay.set_state(False)
        except Exception as exc:
            logger.error("Auto-off failed to switch the relay: %s", exc)
        finally:
            with self._lock:
                self._light_timer = None
                self._light_on_since = None

    # ---------- reporting ----------

    def status(self):
        with self._lock:
            now = self._now()
            self._roll_quota_if_needed(now)
            allowed, reason = self.can_dispense()
            return {
                "treats_allowed": allowed,
                "reason": reason,
                "daylight": self.is_daylight(),
                "treats_today": self._dispense_count,
                "treats_remaining": max(0, self.treat_daily_quota - self._dispense_count),
                "daily_quota": self.treat_daily_quota,
                "cooldown_seconds": self.treat_cooldown,
                "last_dispense": self._last_dispense.isoformat() if self._last_dispense else None,
                "light_auto_off_minutes": self.light_auto_off_minutes,
                "light_on_since": self._light_on_since.isoformat() if self._light_on_since else None,
            }
