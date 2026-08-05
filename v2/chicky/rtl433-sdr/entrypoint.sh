#!/bin/sh
# 433.92MHz SDR receiver (Nooelec NESDR Smart v5 on chicky's USB).
#
# Mirrors the rtl_433 deployment that ran in-cluster on jerry: fixed tune, no
# device filter, same MQTT topic layout so Telegraf, prometheus-rf and Home
# Assistant keep consuming unchanged. The broker is mosquitto-lb's
# authenticated listener; MQTT_HOST/MQTT_USER/MQTT_PASS are balena service
# variables, never committed here.
set -eu

: "${MQTT_HOST:?set as a balena service variable}"
: "${MQTT_USER:?set as a balena service variable}"
: "${MQTT_PASS:?set as a balena service variable}"

exec rtl_433 \
  -f 433.92M \
  -M time:iso:utc \
  -M level \
  -F "mqtt://${MQTT_HOST}:${MQTT_PORT:-1883},user=${MQTT_USER},pass=${MQTT_PASS},retain=1,events=rtl433/events,devices=rtl433/devices[/model][/id]"
