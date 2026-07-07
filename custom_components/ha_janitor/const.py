"""Constants for HA Janitor."""

from __future__ import annotations

DOMAIN = "ha_janitor"
NAME = "HA Janitor"
VERSION = "0.1.0"

DATA_WEBSOCKET_REGISTERED = "websocket_registered"

PROTECTED_DOMAINS = {
    "automation",
    "script",
    "scene",
    "input_boolean",
    "input_number",
    "input_select",
    "input_text",
    "counter",
    "timer",
    "schedule",
    "person",
    "zone",
    "sun",
    "weather",
    "calendar",
    "update",
    "backup",
}

STALE_REVIEW_DAYS = 30
STALE_WARN_DAYS = 7
