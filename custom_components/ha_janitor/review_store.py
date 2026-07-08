"""Persistent review-state store for HA Janitor v0.3."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORE_VERSION = 1
STORE_KEY = f"{DOMAIN}.review_state"
VALID_DISPOSITIONS = {
    "unreviewed",
    "reviewed",
    "keep",
    "ignore",
    "candidate_disable",
    "candidate_delete_later",
    "do_not_touch",
}


def _now_iso() -> str:
    """Return an ISO timestamp."""
    return datetime.now(timezone.utc).isoformat()


class ReviewStore:
    """Store user review/disposition state for entities."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise the store."""
        self._store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, STORE_KEY)
        self._data: dict[str, Any] | None = None

    async def async_load(self) -> dict[str, Any]:
        """Load data from storage."""
        if self._data is None:
            self._data = await self._store.async_load() or {"entities": {}}
            self._data.setdefault("entities", {})
        return self._data

    async def async_get_all(self) -> dict[str, Any]:
        """Return all review state."""
        data = await self.async_load()
        return data

    async def async_get_entity(self, entity_id: str) -> dict[str, Any]:
        """Return review state for an entity."""
        data = await self.async_load()
        return data.get("entities", {}).get(entity_id, {"disposition": "unreviewed", "note": ""})

    async def async_set_entity(
        self,
        entity_id: str,
        disposition: str,
        note: str | None = None,
        ignore_until: str | None = None,
    ) -> dict[str, Any]:
        """Set review state for an entity."""
        if disposition not in VALID_DISPOSITIONS:
            raise ValueError(f"Invalid disposition: {disposition}")

        data = await self.async_load()
        existing = data["entities"].get(entity_id, {})
        row = {
            "entity_id": entity_id,
            "disposition": disposition,
            "note": existing.get("note", "") if note is None else note,
            "ignore_until": ignore_until,
            "updated_at": _now_iso(),
        }
        data["entities"][entity_id] = row
        await self._store.async_save(data)
        return row

    async def async_clear_entity(self, entity_id: str) -> None:
        """Clear review state for an entity."""
        data = await self.async_load()
        data.get("entities", {}).pop(entity_id, None)
        await self._store.async_save(data)

    async def async_merge_entity_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Merge review state into entity audit rows."""
        data = await self.async_load()
        states = data.get("entities", {})
        for row in rows:
            entity_id = row.get("entity_id")
            state = states.get(entity_id, {}) if entity_id else {}
            row["disposition"] = state.get("disposition", "unreviewed")
            row["review_note"] = state.get("note", "")
            row["ignore_until"] = state.get("ignore_until")
            row["review_updated_at"] = state.get("updated_at")
        return rows

    async def async_counts(self) -> dict[str, int]:
        """Return counts by disposition."""
        data = await self.async_load()
        counts: dict[str, int] = {key: 0 for key in VALID_DISPOSITIONS}
        for row in data.get("entities", {}).values():
            disposition = row.get("disposition", "unreviewed")
            counts[disposition] = counts.get(disposition, 0) + 1
        return counts
