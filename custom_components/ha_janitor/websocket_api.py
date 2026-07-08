"""WebSocket API for HA Janitor."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .scanner import JanitorScanner


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register HA Janitor WebSocket commands."""
    websocket_api.async_register_command(hass, websocket_get_summary)
    websocket_api.async_register_command(hass, websocket_get_entities)
    websocket_api.async_register_command(hass, websocket_get_devices)
    websocket_api.async_register_command(hass, websocket_get_integrations)
    websocket_api.async_register_command(hass, websocket_get_references)
    websocket_api.async_register_command(hass, websocket_get_broken_references)


@websocket_api.websocket_command({vol.Required("type"): "ha_janitor/get_summary"})
@websocket_api.async_response
async def websocket_get_summary(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Return audit summary."""
    connection.send_result(msg["id"], JanitorScanner(hass).build_summary())


@websocket_api.websocket_command({vol.Required("type"): "ha_janitor/get_entities", vol.Optional("limit"): vol.Any(int, None)})
@websocket_api.async_response
async def websocket_get_entities(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Return entity audit rows."""
    rows = JanitorScanner(hass).build_entities()
    limit = msg.get("limit")
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]
    connection.send_result(msg["id"], rows)


@websocket_api.websocket_command({vol.Required("type"): "ha_janitor/get_devices", vol.Optional("limit"): vol.Any(int, None)})
@websocket_api.async_response
async def websocket_get_devices(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Return device audit rows."""
    rows = JanitorScanner(hass).build_devices()
    limit = msg.get("limit")
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]
    connection.send_result(msg["id"], rows)


@websocket_api.websocket_command({vol.Required("type"): "ha_janitor/get_integrations", vol.Optional("limit"): vol.Any(int, None)})
@websocket_api.async_response
async def websocket_get_integrations(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Return integration/config-entry audit rows."""
    rows = JanitorScanner(hass).build_integrations()
    limit = msg.get("limit")
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]
    connection.send_result(msg["id"], rows)


@websocket_api.websocket_command({vol.Required("type"): "ha_janitor/get_references"})
@websocket_api.async_response
async def websocket_get_references(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Return full reference scan payload."""
    connection.send_result(msg["id"], JanitorScanner(hass).build_reference_scan())


@websocket_api.websocket_command({vol.Required("type"): "ha_janitor/get_broken_references", vol.Optional("limit"): vol.Any(int, None)})
@websocket_api.async_response
async def websocket_get_broken_references(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Return broken reference rows."""
    rows = JanitorScanner(hass).build_broken_references()
    limit = msg.get("limit")
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]
    connection.send_result(msg["id"], rows)
