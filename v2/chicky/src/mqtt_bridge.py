#!/usr/bin/env python3
"""MQTT bridge: the coop dials OUT to the broker instead of listening.

chook.cam went dark because the public VPS had to reach INTO the coop VLAN.
This flips that for the control path too. The Pi opens an outbound connection
to the cluster broker; nothing on the internet needs a route to it, and the
inbound HTTP port can eventually be closed.

Follows the coopi/coop-door pattern: paho v2 callbacks, a last-will for
availability, and retained Home Assistant discovery so entities appear on
their own.

Everything here is optional. With no MQTT_HOST set the bridge does nothing and
the controller runs exactly as before.
"""

import json
import logging
import os
import threading

logger = logging.getLogger(__name__)

DEVICE_ID = "chickenfeed_coop"
DEVICE = {
    "identifiers": [DEVICE_ID],
    "name": "Chicken Coop",
    "manufacturer": "lmacka",
    "model": "chicky",
}


class MqttBridge:
    def __init__(self, servo, relay, sensors, safety):
        self.servo = servo
        self.relay = relay
        self.sensors = sensors
        self.safety = safety
        self.client = None
        self._stop = threading.Event()

        self.host = os.getenv("MQTT_HOST")
        self.port = int(os.getenv("MQTT_PORT", "1883"))
        self.user = os.getenv("MQTT_USER")
        self.password = os.getenv("MQTT_PASS")
        self.base = os.getenv("MQTT_BASE_TOPIC", "chickenfeed/coop")
        self.prefix = os.getenv("MQTT_DISCOVERY_PREFIX", "homeassistant")
        self.interval = int(os.getenv("MQTT_PUBLISH_INTERVAL", "30"))

    # ---------- topics ----------

    def t(self, suffix):
        return f"{self.base}/{suffix}"

    # ---------- lifecycle ----------

    def start(self):
        if not self.host:
            logger.info("MQTT not configured (no MQTT_HOST); running HTTP-only")
            return
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            logger.error("paho-mqtt not installed; MQTT bridge disabled")
            return

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="chicky")
        if self.user:
            client.username_pw_set(self.user, self.password)
        client.will_set(self.t("availability"), "offline", qos=1, retain=True)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.reconnect_delay_set(min_delay=1, max_delay=60)
        self.client = client
        client.connect_async(self.host, self.port, keepalive=60)
        client.loop_start()
        threading.Thread(target=self._publish_loop, daemon=True).start()
        logger.info("MQTT bridge started for %s:%s", self.host, self.port)

    def stop(self):
        self._stop.set()
        if self.client is not None:
            try:
                self.client.publish(self.t("availability"), "offline", qos=1, retain=True)
                self.client.loop_stop()
                self.client.disconnect()
            except Exception as exc:
                logger.error("MQTT shutdown error: %s", exc)

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties):
        if reason_code != 0:
            logger.error("MQTT connection failed: %s", reason_code)
            return
        client.publish(self.t("availability"), "online", qos=1, retain=True)
        self._publish_discovery()
        client.subscribe(self.t("light/set"), qos=1)
        client.subscribe(self.t("treat/set"), qos=1)
        self._publish_state()
        logger.info("MQTT connected; discovery published, commands subscribed")

    # ---------- discovery ----------

    def _sensor(self, key, name, unit, device_class, template):
        return {
            "topic": f"{self.prefix}/sensor/{DEVICE_ID}_{key}/config",
            "payload": {
                "name": name,
                "unique_id": f"{DEVICE_ID}_{key}",
                "state_topic": self.t("climate"),
                "availability_topic": self.t("availability"),
                "unit_of_measurement": unit,
                "device_class": device_class,
                "state_class": "measurement",
                "value_template": template,
                "device": DEVICE,
            },
        }

    def _publish_discovery(self):
        entities = [
            self._sensor("temperature", "Coop Temperature", "°C", "temperature", "{{ value_json.temperature }}"),
            self._sensor("humidity", "Coop Humidity", "%", "humidity", "{{ value_json.humidity }}"),
            self._sensor("pressure", "Coop Pressure", "hPa", "atmospheric_pressure", "{{ value_json.pressure }}"),
            self._sensor("light", "Coop Light Level", "lx", "illuminance", "{{ value_json.light }}"),
            {
                "topic": f"{self.prefix}/sensor/{DEVICE_ID}_treats_today/config",
                "payload": {
                    "name": "Treats Dispensed Today",
                    "unique_id": f"{DEVICE_ID}_treats_today",
                    "state_topic": self.t("status"),
                    "availability_topic": self.t("availability"),
                    "state_class": "total_increasing",
                    "icon": "mdi:food-drumstick",
                    "value_template": "{{ value_json.treats_today }}",
                    "device": DEVICE,
                },
            },
            {
                "topic": f"{self.prefix}/binary_sensor/{DEVICE_ID}_treats_allowed/config",
                "payload": {
                    "name": "Treats Allowed",
                    "unique_id": f"{DEVICE_ID}_treats_allowed",
                    "state_topic": self.t("status"),
                    "availability_topic": self.t("availability"),
                    "icon": "mdi:shield-check",
                    "value_template": "{{ 'ON' if value_json.treats_allowed else 'OFF' }}",
                    "device": DEVICE,
                },
            },
            {
                "topic": f"{self.prefix}/switch/{DEVICE_ID}_light/config",
                "payload": {
                    "name": "Coop Light",
                    "unique_id": f"{DEVICE_ID}_light",
                    "command_topic": self.t("light/set"),
                    "state_topic": self.t("light/state"),
                    "availability_topic": self.t("availability"),
                    "payload_on": "ON",
                    "payload_off": "OFF",
                    "icon": "mdi:lightbulb",
                    "device": DEVICE,
                },
            },
            {
                "topic": f"{self.prefix}/button/{DEVICE_ID}_treat/config",
                "payload": {
                    "name": "Dispense Treat",
                    "unique_id": f"{DEVICE_ID}_treat",
                    "command_topic": self.t("treat/set"),
                    "availability_topic": self.t("availability"),
                    "icon": "mdi:food-drumstick",
                    "device": DEVICE,
                },
            },
        ]
        for ent in entities:
            self.client.publish(ent["topic"], json.dumps(ent["payload"]), qos=1, retain=True)

    # ---------- publishing ----------

    def _publish_state(self):
        try:
            self.client.publish(self.t("status"), json.dumps(self.safety.status()), qos=1, retain=True)
            if self.relay is not None:
                state = "ON" if getattr(self.relay, "light_state", False) else "OFF"
                self.client.publish(self.t("light/state"), state, qos=1, retain=True)
        except Exception as exc:
            logger.error("Failed to publish state: %s", exc)

    def _publish_climate(self):
        try:
            if self.sensors is None:
                return
            readings = self.sensors.get_all_readings()
            payload = {k: readings.get(k) for k in ("temperature", "humidity", "pressure", "light")}
            self.client.publish(self.t("climate"), json.dumps(payload), qos=0, retain=True)
        except Exception as exc:
            logger.error("Failed to publish climate: %s", exc)

    def _publish_loop(self):
        while not self._stop.wait(self.interval):
            if self.client is None:
                continue
            self._publish_climate()
            self._publish_state()

    # ---------- commands ----------

    def _on_message(self, _client, _userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode("utf-8", "ignore").strip()
        logger.info("MQTT command on %s: %s", topic, payload)
        # Actuation runs on a worker thread so a blocking servo sweep never
        # stalls the MQTT network loop.
        if topic == self.t("treat/set"):
            threading.Thread(target=self._do_treat, daemon=True).start()
        elif topic == self.t("light/set"):
            threading.Thread(target=self._do_light, args=(payload.upper() == "ON",), daemon=True).start()
        else:
            logger.warning("Ignoring unknown MQTT topic: %s", topic)

    def _do_treat(self):
        allowed, reason = self.safety.begin_dispense()
        if not allowed:
            logger.warning("Treat refused by safety envelope: %s", reason)
            self._publish_state()
            return
        ok = False
        try:
            if self.servo is not None:
                self.servo.dispense_treat()
            ok = True
            logger.info("Treat dispensed via MQTT")
        except Exception as exc:
            logger.error("Treat dispense failed: %s", exc)
        finally:
            self.safety.end_dispense(ok)
            self._publish_state()

    def _do_light(self, on):
        try:
            if self.relay is not None:
                self.relay.set_state(on)
            if on:
                self.safety.note_light_on()
            else:
                self.safety.note_light_off()
        except Exception as exc:
            logger.error("Light switch failed: %s", exc)
        finally:
            self._publish_state()
