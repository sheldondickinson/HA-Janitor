"""HA Janitor integration setup."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_WEBSOCKET_REGISTERED, DOMAIN
from .websocket_api import async_register_websocket_api


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Janitor from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "entry": entry,
    }

    if not hass.data[DOMAIN].get(DATA_WEBSOCKET_REGISTERED):
        async_register_websocket_api(hass)
        hass.data[DOMAIN][DATA_WEBSOCKET_REGISTERED] = True

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload HA Janitor."""
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True
