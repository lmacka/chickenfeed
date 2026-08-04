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
from datetime import datetime, timedelta
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
        self.treat_daily_quota = _env_int("TREAT_DAILY_QUOTA", 6)
        # Paced mode spreads the daily quota evenly through the daylight
        # window instead of allowing a burst: gap = daylight / quota. The
        # cooldown above remains the floor.
        self.treat_paced = os.getenv("TREAT_PACED", "true").lower() != "false"
        self.light_auto_off_minutes = _env_int("LIGHT_AUTO_OFF_MINUTES", 30)
        self.daylight_only = os.getenv("TREAT_DAYLIGHT_ONLY", "true").lower() != "false"
        # Minimum gap between light switches. The relay has no mechanical guard
        # of its own, so without this an unauthenticated caller can chatter a
        # mains relay at request rate.
        self.light_cooldown = _env_int("LIGHT_COOLDOWN_SECONDS", 5)
        # Total minutes the light may be on across one night, counted from
        # sunset to sunrise and persisted. Chickens need real darkness; this is
        # what stops the light being held on until dawn.
        self.light_night_budget_minutes = _env_int("LIGHT_NIGHT_BUDGET_MINUTES", 15)

        self._last_dispense = None
        self._dispense_count = 0
        self._quota_day = None
        self._dispensing = False
        self._light_timer = None
        self._light_on_since = None
        self._last_light_change = None
        self._light_night_seconds = 0.0
        self._light_night_key = None

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
            # Persisted so a restart cannot hand back a fresh night's budget.
            self._light_night_key = data.get("light_night_key")
            self._light_night_seconds = float(data.get("light_night_seconds", 0.0))
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
                    "light_night_key": self._light_night_key,
                    "light_night_seconds": self._light_night_seconds,
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

    def _sun_window(self, now, days_ahead=0):
        """(sunrise, sunset) for now.date() + days_ahead, in the coop tz.

        Uses a real sunrise/sunset calculation when astral is available, and a
        fixed local-time window otherwise. A broken almanac must not brick the
        feeder.
        """
        date = now.date() + timedelta(days=days_ahead)
        try:
            from astral import LocationInfo
            from astral.sun import sun
            loc = LocationInfo(
                name="coop", region="AU", timezone=self.timezone,
                latitude=self.latitude, longitude=self.longitude,
            )
            times = sun(loc.observer, date=date, tzinfo=now.tzinfo)
            return times["sunrise"], times["sunset"]
        except Exception as exc:
            logger.warning("Sun calculation unavailable (%s); using fixed window", exc)
            return (
                datetime.combine(date, FALLBACK_DAWN, tzinfo=now.tzinfo),
                datetime.combine(date, FALLBACK_DUSK, tzinfo=now.tzinfo),
            )

    def is_daylight(self):
        """True when the sun is up at the coop.

        The point of the rule is the chickens' sleep schedule, so it keys off
        the sun rather than measured lux: switching the coop light on at
        midnight must not unlock treats.
        """
        now = self._now()
        sunrise, sunset = self._sun_window(now)
        return sunrise <= now <= sunset

    def _pace_seconds(self, now):
        """Minimum gap between treats: daylight / quota, floored by cooldown."""
        if not self.treat_paced:
            return self.treat_cooldown
        sunrise, sunset = self._sun_window(now)
        window = max(0.0, (sunset - sunrise).total_seconds())
        return max(float(self.treat_cooldown), window / max(1, self.treat_daily_quota))

    def _next_allowed(self, now):
        """When the next treat becomes possible, or None if allowed right now.

        Best effort: if state is inconsistent (clock jumps, tz changes) the
        answer degrades to None rather than raising, because this feeds a UI
        countdown, not the gate itself.
        """
        allowed, _ = self.can_dispense()
        if allowed:
            return None
        try:
            sunrise, sunset = self._sun_window(now)
            tomorrow_sunrise = self._sun_window(now, days_ahead=1)[0]
            if self.daylight_only and now < sunrise:
                return sunrise
            if self.daylight_only and now > sunset:
                return tomorrow_sunrise
            if self._dispense_count >= self.treat_daily_quota:
                return tomorrow_sunrise
            if self._last_dispense is not None:
                cand = self._last_dispense + timedelta(seconds=self._pace_seconds(now))
                if self.daylight_only and cand > sunset:
                    return tomorrow_sunrise
                return cand
        except Exception as exc:
            logger.warning("Could not compute next_allowed (%s)", exc)
        return None

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
                gap = self._pace_seconds(now)
                elapsed = (now - self._last_dispense).total_seconds()
                if elapsed < gap:
                    wait = int(gap - elapsed) + 1
                    if wait > 90:
                        return False, f"spacing treats out, next one in {wait // 60 + 1} min"
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

    def _night_key(self, now):
        """Identifies one dusk-to-dawn night, so a budget spans midnight.

        Before sunrise still belongs to the previous calendar day's night.
        """
        try:
            sunrise, _ = self._sun_window(now)
            if now < sunrise:
                return (now.date() - timedelta(days=1)).isoformat()
        except Exception:
            pass
        return now.date().isoformat()

    def _roll_night_if_needed(self, now):
        key = self._night_key(now)
        if self._light_night_key != key:
            self._light_night_key = key
            self._light_night_seconds = 0.0
            self._save()

    def _night_seconds_remaining(self, now):
        self._roll_night_if_needed(now)
        budget = max(0, self.light_night_budget_minutes) * 60
        return max(0.0, budget - self._light_night_seconds)

    def can_light(self, on):
        """Return (allowed, reason) for a light request.

        Turning the light OFF is always allowed: a safety gate must never be
        the reason a light stays on. Turning it ON is rate limited always, and
        at night is additionally capped by a cumulative budget, so the coop
        cannot be lit until dawn by anyone, including a fully compromised web
        app.
        """
        with self._lock:
            now = self._now()
            if not on:
                return True, "ok"

            if self._last_light_change is not None:
                elapsed = (now - self._last_light_change).total_seconds()
                if elapsed < self.light_cooldown:
                    return False, f"the light needs a moment, try again in {int(self.light_cooldown - elapsed) + 1}s"

            if not self.is_daylight():
                if self._night_seconds_remaining(now) <= 0:
                    return False, "the chickens need darkness, the light has had its time tonight"

            return True, "ok"

    def note_light_on(self):
        """Arm the auto-off deadline. Does NOT extend an existing one.

        Re-arming on every ON was the bug: re-sending ON just inside the
        window held the light on indefinitely. The deadline is set by the
        first ON and runs to completion; at night it is also clamped to
        whatever is left of the night's budget.
        """
        with self._lock:
            now = self._now()
            self._last_light_change = now
            if self._light_timer is not None:
                # A deadline is already running. Leave it alone.
                return
            self._light_on_since = now
            if self.light_auto_off_minutes <= 0:
                logger.warning(
                    "LIGHT_AUTO_OFF_MINUTES is %s: the light has no auto-off",
                    self.light_auto_off_minutes,
                )
                return
            seconds = self.light_auto_off_minutes * 60
            if not self.is_daylight():
                seconds = min(seconds, self._night_seconds_remaining(now))
            if seconds <= 0:
                # Budget already spent; the caller should not have got here.
                seconds = 1
            self._light_timer = threading.Timer(seconds, self._auto_off)
            self._light_timer.daemon = True
            self._light_timer.start()
            logger.info("Coop light on; auto-off in %.0f s", seconds)

    def note_light_off(self):
        with self._lock:
            self._cancel_light_timer()
            self._last_light_change = self._now()
            self._account_light_time()

    def _cancel_light_timer(self):
        if self._light_timer is not None:
            self._light_timer.cancel()
            self._light_timer = None

    def _account_light_time(self):
        """Bank any night-time the light has just been on. Lock held."""
        if self._light_on_since is None:
            self._light_on_since = None
            return
        now = self._now()
        elapsed = max(0.0, (now - self._light_on_since).total_seconds())
        self._light_on_since = None
        if elapsed and not self.is_daylight():
            self._roll_night_if_needed(now)
            self._light_night_seconds += elapsed
            self._save()

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
                self._account_light_time()

    # ---------- reporting ----------

    def status(self):
        with self._lock:
            now = self._now()
            self._roll_quota_if_needed(now)
            allowed, reason = self.can_dispense()
            nxt = self._next_allowed(now)
            return {
                "treats_allowed": allowed,
                "reason": reason,
                "daylight": self.is_daylight(),
                "treats_today": self._dispense_count,
                "treats_remaining": max(0, self.treat_daily_quota - self._dispense_count),
                "daily_quota": self.treat_daily_quota,
                "cooldown_seconds": self.treat_cooldown,
                "next_allowed_at": nxt.isoformat() if nxt else None,
                "last_dispense": self._last_dispense.isoformat() if self._last_dispense else None,
                "light_auto_off_minutes": self.light_auto_off_minutes,
                "light_on_since": self._light_on_since.isoformat() if self._light_on_since else None,
                "light_allowed": self.can_light(True)[0],
                "light_night_seconds_remaining": int(self._night_seconds_remaining(now)),
            }
