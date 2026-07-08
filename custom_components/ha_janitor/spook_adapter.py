"""Optional Spook adapter for HA Janitor safe actions.

HA Janitor never depends on Spook. This adapter only detects and calls safe
Spook/Home Assistant service actions when they exist.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

SUPPORTED_ENTITY_ACTIONS = {
    "disable_entity": ("homeassistant", "disable_entity"),
    "enable_entity": ("homeassistant", "enable_entity"),
    "hide_entity": ("homeassistant", "hide_entity"),
    "unhide_entity": ("homeassistant", "unhide_entity"),
}


class SpookAdapter:
    """Detect and call optional Spook-backed safe services."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise adapter."""
        self.hass = hass

    def capabilities(self) -> dict[str, Any]:
        """Return available safe-action capabilities."""
        services = self.hass.services.async_services()
        support: dict[str, bool] = {}
        for action, (domain, service) in SUPPORTED_ENTITY_ACTIONS.items():
            support[action] = domain in services and service in services[domain]

        return {
            "spook_entity_actions_available": any(support.values()),
            "supports": support,
            "note": "Only safe entity actions are exposed. Delete/purge/destructive actions are intentionally not supported.",
        }

    async def async_entity_action(self, action: str, entity_ids: list[str]) -> dict[str, Any]:
        """Run a safe entity action against one or more entity IDs."""
        if action not in SUPPORTED_ENTITY_ACTIONS:
            raise ValueError(f"Unsupported action: {action}")
        if not entity_ids:
            raise ValueError("No entity IDs supplied")

        domain, service = SUPPORTED_ENTITY_ACTIONS[action]
        caps = self.capabilities()
        if not caps["supports"].get(action):
            raise RuntimeError(f"Required service is not available: {domain}.{service}")

        results: list[dict[str, Any]] = []
        for entity_id in entity_ids:
            try:
                await self.hass.services.async_call(
                    domain,
                    service,
                    {"entity_id": entity_id},
                    blocking=True,
                )
                results.append({"entity_id": entity_id, "ok": True, "error": None})
            except Exception as err:  # noqa: BLE001 - return per-entity action failure to UI
                results.append({"entity_id": entity_id, "ok": False, "error": str(err)})

        return {
            "action": action,
            "service": f"{domain}.{service}",
            "requested": len(entity_ids),
            "succeeded": sum(1 for row in results if row["ok"]),
            "failed": sum(1 for row in results if not row["ok"]),
            "results": results,
        }
