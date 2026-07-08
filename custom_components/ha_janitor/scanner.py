"""Read-only scanner for HA Janitor v0.4."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .recorder_analyser import RecorderAnalyser
from .reference_scanner import ReferenceScanner
from .scoring import score_device, score_entity

BAD_STATES = {STATE_UNAVAILABLE, STATE_UNKNOWN}


def _as_iso(value: datetime | None) -> str | None:
    """Return an ISO timestamp or None."""
    if value is None:
        return None
    return value.isoformat()


def _entry_state_to_string(state: Any) -> str:
    """Normalise a config entry state enum/string across HA versions."""
    return getattr(state, "value", str(state))


def _duration_seconds(state: State | None, now: datetime) -> float | None:
    """Return seconds since last state change."""
    if state is None or state.last_changed is None:
        return None
    return max(0.0, (now - state.last_changed).total_seconds())


def _safe_attr(obj: Any, attr: str, default: Any = None) -> Any:
    """Read an attribute safely across HA versions."""
    return getattr(obj, attr, default)


def _registry_items(registry_mapping: Any) -> dict[str, Any]:
    """Return a normal dict from HA registry mapping-like containers."""
    try:
        return dict(registry_mapping)
    except TypeError:
        return {item.entity_id: item for item in registry_mapping.values()}


class JanitorScanner:
    """Build read-only audit data from Home Assistant registries and states."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise the scanner."""
        self.hass = hass
        self.entity_registry = er.async_get(hass)
        self.device_registry = dr.async_get(hass)
        self.area_registry = ar.async_get(hass)
        self.now = dt_util.utcnow()
        self._reference_scan: dict[str, Any] | None = None
        self._recorder_summary: dict[str, Any] | None = None

    def build_entities(self, include_references: bool = True, include_recorder: bool = True) -> list[dict[str, Any]]:
        """Return entity audit rows."""
        registry_entities = _registry_items(self.entity_registry.entities)
        state_entity_ids = set(self.hass.states.async_entity_ids())
        all_entity_ids = sorted(set(registry_entities) | state_entity_ids)
        reference_scan = self.build_reference_scan(all_entity_ids) if include_references else None
        reference_index = (reference_scan or {}).get("references", {})

        rows: list[dict[str, Any]] = []
        for entity_id in all_entity_ids:
            references = reference_index.get(entity_id, [])
            rows.append(
                self._build_entity_row(
                    entity_id,
                    registry_entities.get(entity_id),
                    references=references,
                    references_scanned=include_references,
                )
            )

        if include_recorder:
            self._recorder_summary = RecorderAnalyser(self.hass).analyse(rows)
        else:
            self._recorder_summary = {"recorder_status": "disabled", "recorder_available": False}

        rows.sort(key=lambda item: (
            item.get("risk") != "review",
            item.get("reference_count", 0) > 0,
            -(item.get("recorder_bad_streak_days") or item.get("duration_current_state_days") or 0),
            item.get("entity_id") or "",
        ))
        return rows

    def build_devices(self, entities: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        """Return device audit rows."""
        if entities is None:
            entities = self.build_entities()

        entities_by_device: dict[str, list[dict[str, Any]]] = {}
        for entity in entities:
            device_id = entity.get("device_id")
            if device_id:
                entities_by_device.setdefault(device_id, []).append(entity)

        config_entries = list(self.hass.config_entries.async_entries())
        rows: list[dict[str, Any]] = []
        for device_id, device in self.device_registry.devices.items():
            linked_entities = entities_by_device.get(device_id, [])
            unavailable_count = sum(1 for item in linked_entities if item.get("state") == STATE_UNAVAILABLE)
            unknown_count = sum(1 for item in linked_entities if item.get("state") == STATE_UNKNOWN)
            disabled_count = sum(1 for item in linked_entities if item.get("disabled"))
            hidden_count = sum(1 for item in linked_entities if item.get("hidden"))
            healthy_count = sum(1 for item in linked_entities if item.get("state") not in BAD_STATES and item.get("state") is not None)
            reference_count = sum(int(item.get("reference_count") or 0) for item in linked_entities)
            max_recorder_bad_streak_days = max((item.get("recorder_bad_streak_days") or 0 for item in linked_entities), default=0)

            config_entry_ids = sorted(str(value) for value in (_safe_attr(device, "config_entries", set()) or set()))
            integration_domains = sorted({entry.domain for entry in config_entries if entry.entry_id in config_entry_ids})
            area_id = _safe_attr(device, "area_id")
            area = self.area_registry.async_get_area(area_id) if area_id else None

            row: dict[str, Any] = {
                "device_id": device_id,
                "name": _safe_attr(device, "name_by_user") or _safe_attr(device, "name"),
                "manufacturer": _safe_attr(device, "manufacturer"),
                "model": _safe_attr(device, "model"),
                "area_id": area_id,
                "area_name": area.name if area else None,
                "config_entry_ids": config_entry_ids,
                "integration_domains": integration_domains,
                "entity_ids": sorted(item["entity_id"] for item in linked_entities),
                "entity_count": len(linked_entities),
                "unavailable_entity_count": unavailable_count,
                "unknown_entity_count": unknown_count,
                "disabled_entity_count": disabled_count,
                "hidden_entity_count": hidden_count,
                "healthy_entity_count": healthy_count,
                "reference_count": reference_count,
                "max_recorder_bad_streak_days": max_recorder_bad_streak_days,
            }
            row.update(score_device(row))
            rows.append(row)

        rows.sort(key=lambda item: (item.get("risk") != "review", -(item.get("max_recorder_bad_streak_days") or 0), item.get("name") or ""))
        return rows

    def build_integrations(self, entities: list[dict[str, Any]] | None = None, devices: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        """Return config-entry/integration audit rows."""
        if entities is None:
            entities = self.build_entities()
        if devices is None:
            devices = self.build_devices(entities)

        rows: list[dict[str, Any]] = []
        for entry in self.hass.config_entries.async_entries():
            entry_entities = [item for item in entities if item.get("config_entry_id") == entry.entry_id]
            entry_devices = [item for item in devices if entry.entry_id in (item.get("config_entry_ids") or [])]
            rows.append({
                "config_entry_id": entry.entry_id,
                "domain": entry.domain,
                "title": entry.title,
                "state": _entry_state_to_string(entry.state),
                "device_count": len(entry_devices),
                "entity_count": len(entry_entities),
                "unavailable_count": sum(1 for item in entry_entities if item.get("state") == STATE_UNAVAILABLE),
                "unknown_count": sum(1 for item in entry_entities if item.get("state") == STATE_UNKNOWN),
                "disabled_count": sum(1 for item in entry_entities if item.get("disabled")),
                "hidden_count": sum(1 for item in entry_entities if item.get("hidden")),
                "reference_count": sum(int(item.get("reference_count") or 0) for item in entry_entities),
                "referenced_entity_count": sum(1 for item in entry_entities if int(item.get("reference_count") or 0) > 0),
                "max_recorder_bad_streak_days": max((item.get("recorder_bad_streak_days") or 0 for item in entry_entities), default=0),
            })

        rows.sort(key=lambda item: (item.get("domain") or "", item.get("title") or ""))
        return rows

    def build_reference_scan(self, known_entity_ids: set[str] | list[str] | None = None) -> dict[str, Any]:
        """Return static reference scan payload, cached per scanner instance."""
        if self._reference_scan is not None:
            return self._reference_scan
        if known_entity_ids is None:
            registry_entities = _registry_items(self.entity_registry.entities)
            known_entity_ids = set(registry_entities) | set(self.hass.states.async_entity_ids())
        self._reference_scan = ReferenceScanner(self.hass, set(known_entity_ids)).scan()
        return self._reference_scan

    def build_broken_references(self) -> list[dict[str, Any]]:
        """Return broken reference rows."""
        scan = self.build_reference_scan()
        rows: list[dict[str, Any]] = []
        for target, refs in scan.get("broken_references", {}).items():
            rows.append({"target": target, "reference_count": len(refs), "references": refs})
        rows.sort(key=lambda item: (-item["reference_count"], item["target"]))
        return rows

    def build_summary(self) -> dict[str, Any]:
        """Return a summary audit payload."""
        entities = self.build_entities()
        devices = self.build_devices(entities)
        integrations = self.build_integrations(entities, devices)
        reference_scan = self.build_reference_scan()
        reference_summary = reference_scan.get("summary", {})
        recorder_summary = self._recorder_summary or {}

        unavailable = [item for item in entities if item.get("state") == STATE_UNAVAILABLE]
        unknown = [item for item in entities if item.get("state") == STATE_UNKNOWN]
        stale_30 = [item for item in entities if item.get("state") in BAD_STATES and (item.get("recorder_bad_streak_days") or item.get("duration_current_state_days") or 0) >= 30]
        review = [item for item in entities if item.get("risk") == "review"]
        protected = [item for item in entities if item.get("risk") == "protected"]
        referenced = [item for item in entities if int(item.get("reference_count") or 0) > 0]

        return {
            "generated_at": dt_util.utcnow().isoformat(),
            "version": "0.4.0",
            "entities_total": len(entities),
            "devices_total": len(devices),
            "integrations_total": len(integrations),
            "entities_unavailable": len(unavailable),
            "entities_unknown": len(unknown),
            "entities_stale_30_days": len(stale_30),
            "entities_review": len(review),
            "entities_protected": len(protected),
            "entities_referenced": len(referenced),
            "entities_unreferenced": len(entities) - len(referenced),
            "broken_reference_targets": reference_summary.get("broken_reference_targets", 0),
            "total_broken_references": reference_summary.get("total_broken_references", 0),
            "files_scanned": reference_summary.get("files_scanned", 0),
            "files_failed": reference_summary.get("files_failed", 0),
            "devices_all_bad": sum(1 for item in devices if item.get("entity_count", 0) > 0 and (item.get("unavailable_entity_count", 0) + item.get("unknown_entity_count", 0)) == item.get("entity_count", 0)),
            "recorder": recorder_summary,
            "note": "v0.4 is read-only and includes static reference scanning plus SQLite recorder duration analysis.",
        }

    def _build_entity_row(self, entity_id: str, entry: Any | None, references: list[dict[str, Any]] | None = None, references_scanned: bool = False) -> dict[str, Any]:
        """Build a single entity row."""
        state = self.hass.states.get(entity_id)
        domain = entity_id.split(".", 1)[0] if "." in entity_id else entity_id
        duration = _duration_seconds(state, self.now)
        references = references or []

        device_id = _safe_attr(entry, "device_id") if entry else None
        device = self.device_registry.async_get(device_id) if device_id else None
        area_id = _safe_attr(entry, "area_id") if entry else None
        if area_id is None and device is not None:
            area_id = _safe_attr(device, "area_id")
        area = self.area_registry.async_get_area(area_id) if area_id else None

        config_entry_id = _safe_attr(entry, "config_entry_id") if entry else None
        integration_domain = _safe_attr(entry, "platform") if entry else None
        registry_name = _safe_attr(entry, "name") if entry else None
        original_name = _safe_attr(entry, "original_name") if entry else None

        row: dict[str, Any] = {
            "entity_id": entity_id,
            "domain": domain,
            "name": registry_name or original_name or (state.name if state else None),
            "state": state.state if state else None,
            "last_changed": _as_iso(state.last_changed if state else None),
            "last_updated": _as_iso(state.last_updated if state else None),
            "duration_current_state_seconds": duration,
            "duration_current_state_days": round(duration / 86400, 2) if duration is not None else None,
            "device_id": device_id,
            "device_name": (_safe_attr(device, "name_by_user") or _safe_attr(device, "name")) if device else None,
            "area_id": area_id,
            "area_name": area.name if area else None,
            "integration_domain": integration_domain,
            "config_entry_id": config_entry_id,
            "entity_category": str(_safe_attr(entry, "entity_category")) if entry and _safe_attr(entry, "entity_category") else None,
            "disabled": bool(_safe_attr(entry, "disabled_by")) if entry else False,
            "hidden": bool(_safe_attr(entry, "hidden_by")) if entry else False,
            "has_registry_entry": entry is not None,
            "has_state": state is not None,
            "has_device": device_id is not None,
            "reference_count": len(references),
            "references": references[:20],
            "references_scanned": references_scanned,
        }
        row.update(score_entity(row))
        return row
