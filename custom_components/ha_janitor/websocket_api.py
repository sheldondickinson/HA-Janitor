"""WebSocket API for HA Janitor."""

from __future__ import annotations

import csv
import io
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .review_store import ReviewStore
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
    websocket_api.async_register_command(hass, websocket_get_review_state)
    websocket_api.async_register_command(hass, websocket_set_entity_review)
    websocket_api.async_register_command(hass, websocket_clear_entity_review)
    websocket_api.async_register_command(hass, websocket_export_entities_csv)


@websocket_api.websocket_command({vol.Required("type"): "ha_janitor/get_summary"})
@websocket_api.async_response
async def websocket_get_summary(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Return audit summary."""
    summary = JanitorScanner(hass).build_summary()
    summary["review_counts"] = await ReviewStore(hass).async_counts()
    connection.send_result(msg["id"], summary)


@websocket_api.websocket_command({vol.Required("type"): "ha_janitor/get_entities", vol.Optional("limit"): vol.Any(int, None)})
@websocket_api.async_response
async def websocket_get_entities(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Return entity audit rows."""
    rows = JanitorScanner(hass).build_entities()
    rows = await ReviewStore(hass).async_merge_entity_rows(rows)
    limit = msg.get("limit")
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]
    connection.send_result(msg["id"], rows)


@websocket_api.websocket_command({vol.Required("type"): "ha_janitor/get_devices", vol.Optional("limit"): vol.Any(int, None)})
@websocket_api.async_response
async def websocket_get_devices(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Return device audit rows."""
    scanner = JanitorScanner(hass)
    entities = await ReviewStore(hass).async_merge_entity_rows(scanner.build_entities())
    rows = scanner.build_devices(entities)
    limit = msg.get("limit")
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]
    connection.send_result(msg["id"], rows)


@websocket_api.websocket_command({vol.Required("type"): "ha_janitor/get_integrations", vol.Optional("limit"): vol.Any(int, None)})
@websocket_api.async_response
async def websocket_get_integrations(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Return integration/config-entry audit rows."""
    scanner = JanitorScanner(hass)
    entities = await ReviewStore(hass).async_merge_entity_rows(scanner.build_entities())
    devices = scanner.build_devices(entities)
    rows = scanner.build_integrations(entities, devices)
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


@websocket_api.websocket_command({vol.Required("type"): "ha_janitor/get_review_state"})
@websocket_api.async_response
async def websocket_get_review_state(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Return persistent review state."""
    connection.send_result(msg["id"], await ReviewStore(hass).async_get_all())


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_janitor/set_entity_review",
        vol.Required("entity_id"): str,
        vol.Required("disposition"): str,
        vol.Optional("note"): vol.Any(str, None),
        vol.Optional("ignore_until"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def websocket_set_entity_review(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Set persistent review state for an entity."""
    try:
        row = await ReviewStore(hass).async_set_entity(
            msg["entity_id"],
            msg["disposition"],
            note=msg.get("note"),
            ignore_until=msg.get("ignore_until"),
        )
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_disposition", str(err))
        return
    connection.send_result(msg["id"], row)


@websocket_api.websocket_command({vol.Required("type"): "ha_janitor/clear_entity_review", vol.Required("entity_id"): str})
@websocket_api.async_response
async def websocket_clear_entity_review(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Clear persistent review state for an entity."""
    await ReviewStore(hass).async_clear_entity(msg["entity_id"])
    connection.send_result(msg["id"], {"cleared": True, "entity_id": msg["entity_id"]})


@websocket_api.websocket_command({vol.Required("type"): "ha_janitor/export_entities_csv"})
@websocket_api.async_response
async def websocket_export_entities_csv(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Return entity audit as CSV text."""
    rows = JanitorScanner(hass).build_entities()
    rows = await ReviewStore(hass).async_merge_entity_rows(rows)
    output = io.StringIO()
    fieldnames = [
        "entity_id", "name", "state", "duration_current_state_days", "risk", "disposition", "review_note",
        "reference_count", "device_name", "area_name", "integration_domain", "recommendation",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    connection.send_result(msg["id"], {"filename": "ha-janitor-entities.csv", "csv": output.getvalue()})
