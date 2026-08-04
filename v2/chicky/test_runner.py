#!/usr/bin/env python3
"""Smoke test for the safety envelope and MQTT bridge.

Runs in mock mode (no hardware). Exercises the rules that keep the chickens
safe regardless of what the web app asks for: cooldown, daily quota, daylight
gate, quota persistence and the light auto-off timer. Also proves the bridge
can reach a real broker.

    MQTT_HOST=... MQTT_USER=... MQTT_PASS=... python test_runner.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import main  # noqa: E402
from src.safety import SafetyEnvelope  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"  [{detail}]" if detail else ""))
    if not cond:
        fails.append(name)


print("=== import ===")
check("module imports", True)
check("mock mode detected", main.HARDWARE_AVAILABLE is False, f"hardware={main.HARDWARE_AVAILABLE}")

print("\n=== safety envelope ===")
s = SafetyEnvelope(relay=None)
st = s.status()
print("  status:", json.dumps(st, indent=2)[:400])
check("status has required keys",
      all(k in st for k in ("treats_allowed", "daylight", "treats_today", "treats_remaining")))
check("daylight is a bool", isinstance(st["daylight"], bool), f"daylight={st['daylight']}")
check("quota read from env", st["daily_quota"] == 3, f"quota={st['daily_quota']}")

print("\n=== cooldown enforcement ===")
s2 = SafetyEnvelope(relay=None)
s2.daylight_only = False  # isolate the cooldown rule from the time of day
s2.treat_paced = False    # and from daylight pacing
a1, r1 = s2.begin_dispense()
check("first dispense allowed", a1, r1)
s2.end_dispense(True)
a2, r2 = s2.begin_dispense()
check("second dispense blocked by cooldown", not a2, r2)
check("cooldown reason is human readable", "cooling down" in r2, r2)

print("\n=== daily quota enforcement ===")
s3 = SafetyEnvelope(relay=None)
s3.daylight_only = False
s3.treat_paced = False
s3.treat_cooldown = 0
for _ in range(3):
    ok, _ = s3.begin_dispense()
    s3.end_dispense(ok)
a4, r4 = s3.begin_dispense()
check("quota of 3 exhausts", not a4, r4)
check("quota reason mentions the limit", "daily treat limit" in r4, r4)
check("treats_remaining hits zero", s3.status()["treats_remaining"] == 0)

print("\n=== quota persists across restart ===")
s4 = SafetyEnvelope(relay=None)
check("counter survived reinstantiation", s4.status()["treats_today"] == 3,
      f"treats_today={s4.status()['treats_today']}")

print("\n=== daylight pacing ===")
sp = SafetyEnvelope(relay=None)
sp.daylight_only = False
sp.treat_paced = True
sp.treat_cooldown = 0
sp._dispense_count = 0
sp._last_dispense = sp._now()
gap = sp._pace_seconds(sp._now())
check("pace gap is daylight/quota, not the cooldown", gap > 60, f"gap={gap:.0f}s")
pa, pr = sp.can_dispense()
check("pacing blocks straight after a treat", not pa, pr)
pst = sp.status()
check("status carries next_allowed_at while blocked",
      pst["next_allowed_at"] is not None, str(pst["next_allowed_at"]))

print("\n=== daylight gate ===")
s5 = SafetyEnvelope(relay=None)
s5.daylight_only = True
s5.treat_cooldown = 0
s5._dispense_count = 0
# Isolate the daylight rule. The constructor loads the state file, which
# holds a recent dispense from the quota section above; with pacing on that
# blocks in broad daylight and this check fails during AEST daytime only.
s5.treat_paced = False
s5._last_dispense = None
allowed, reason = s5.can_dispense()
is_day = s5.is_daylight()
check("daylight gate agrees with can_dispense", allowed == is_day or not is_day,
      f"daylight={is_day} allowed={allowed} reason={reason}")
if not is_day:
    check("night refusal mentions sleeping", "asleep" in reason, reason)

print("\n=== light auto-off timer ===")


class FakeRelay:
    def __init__(self):
        self.light_state = False
        self.calls = []

    def set_state(self, v):
        self.light_state = v
        self.calls.append(v)


fr = FakeRelay()
s6 = SafetyEnvelope(relay=fr)
s6.light_auto_off_minutes = 0.02 / 60  # ~20ms, just to prove the timer fires
s6.note_light_on()
time.sleep(0.5)
check("auto-off switched the relay off", fr.calls and fr.calls[-1] is False, f"calls={fr.calls}")

print("\n=== light: the deadline does not extend ===")
# The bug this replaces: note_light_on() cancelled and restarted the timer, so
# re-sending ON just inside the window held the light on until dawn.
fr2 = FakeRelay()
s7 = SafetyEnvelope(relay=fr2)
s7.light_auto_off_minutes = 0.6 / 60  # ~600ms
s7.light_cooldown = 0
s7.note_light_on()
for _ in range(6):  # keep asking, well inside the deadline
    time.sleep(0.15)
    s7.note_light_on()
time.sleep(0.6)
check("repeated ON cannot hold the light past its deadline",
      fr2.calls and fr2.calls[-1] is False, f"calls={fr2.calls}")

print("\n=== light: night budget ===")
fr3 = FakeRelay()
s8 = SafetyEnvelope(relay=fr3)
s8.light_cooldown = 0
s8.is_daylight = lambda: False        # force night
s8.light_night_budget_minutes = 1
s8._light_night_key = "forced"
s8._light_night_seconds = 0.0
allowed, _ = s8.can_light(True)
check("light allowed at night while budget remains", allowed)
s8._light_night_seconds = 61.0        # budget spent
allowed, reason = s8.can_light(True)
check("light refused once the night budget is spent", not allowed, reason)
allowed, _ = s8.can_light(False)
check("turning the light OFF is never refused", allowed)

print("\n=== light: cooldown ===")
s9 = SafetyEnvelope(relay=None)
s9.is_daylight = lambda: True
s9.light_cooldown = 30
s9.note_light_on()
allowed, reason = s9.can_light(True)
check("light cooldown blocks relay chatter", not allowed, reason)

print("\n=== MQTT bridge against the real broker ===")
# Skipped without a broker, so CI can assert a clean exit rather than
# tolerating a non-zero one and masking real failures along with it.
if not os.getenv("MQTT_HOST"):
    print("SKIP  broker checks (MQTT_HOST unset)")
    print("\n=== RESULT ===")
    if fails:
        print("FAILURES:", ", ".join(fails))
        sys.exit(1)
    print("all checks passed (broker leg skipped)")
    sys.exit(0)

bridge = main.mqtt_bridge
bridge.start()
connected = False
for _ in range(30):
    if bridge.client is not None and bridge.client.is_connected():
        connected = True
        break
    time.sleep(0.5)
check("connected to broker", connected, f"{bridge.host}:{bridge.port}")

if connected:
    bridge._publish_climate()
    bridge._publish_state()
    time.sleep(1.5)
    check("published without raising", True)
    bridge.stop()

print("\n=== RESULT ===")
if fails:
    print("FAILURES:", ", ".join(fails))
    sys.exit(1)
print("all checks passed")
