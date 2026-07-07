"""Conservative v0.1 scoring for HA Janitor."""

from __future__ import annotations

from .const import PROTECTED_DOMAINS, STALE_REVIEW_DAYS, STALE_WARN_DAYS

BAD_STATES = {"unavailable", "unknown"}


def score_entity(entity: dict) -> dict:
    """Return risk/recommendation metadata for an entity audit row.

    v0.1 intentionally avoids declaring anything safe to delete because it does
    not yet scan automations, scripts, scenes, templates or dashboards.
    """
    domain = entity.get("domain")
    state = entity.get("state")
    disabled = entity.get("disabled")
    hidden = entity.get("hidden")
    duration_days = entity.get("duration_current_state_days") or 0
    has_device = entity.get("has_device")

    reasons: list[str] = []

    if domain in PROTECTED_DOMAINS:
        return {
            "risk": "protected",
            "recommendation": "Do not touch automatically",
            "reasons": [f"Protected domain: {domain}"],
        }

    if disabled:
        reasons.append("Entity is already disabled")
        return {
            "risk": "info",
            "recommendation": "Already disabled; review only if it still causes clutter",
            "reasons": reasons,
        }

    if hidden:
        reasons.append("Entity is hidden")

    if state in BAD_STATES and duration_days >= STALE_REVIEW_DAYS:
        reasons.append(f"State has been {state} for {duration_days:.1f} days")
        if not has_device:
            reasons.append("Entity is not linked to a device")
        return {
            "risk": "review",
            "recommendation": "Review as stale; v0.1 recommends disable-first only after manual checks",
            "reasons": reasons,
        }

    if state in BAD_STATES and duration_days >= STALE_WARN_DAYS:
        reasons.append(f"State has been {state} for {duration_days:.1f} days")
        return {
            "risk": "review",
            "recommendation": "Review if this device should still exist",
            "reasons": reasons,
        }

    if not has_device:
        reasons.append("Entity is not linked to a device")
        return {
            "risk": "review",
            "recommendation": "Review orphan-style entity metadata",
            "reasons": reasons,
        }

    return {
        "risk": "info",
        "recommendation": "No v0.1 cleanup signal",
        "reasons": reasons or ["No stale-state signal found"],
    }


def score_device(device: dict) -> dict:
    """Return risk/recommendation metadata for a device audit row."""
    entity_count = device.get("entity_count") or 0
    bad_count = (device.get("unavailable_entity_count") or 0) + (
        device.get("unknown_entity_count") or 0
    )
    all_bad = entity_count > 0 and bad_count == entity_count

    reasons: list[str] = []

    if entity_count == 0:
        return {
            "risk": "review",
            "recommendation": "Review device with no entities",
            "reasons": ["Device has no linked entities"],
        }

    if all_bad:
        reasons.append("All linked entities are unavailable or unknown")
        return {
            "risk": "review",
            "recommendation": "Review device; likely candidate for disable-first workflow after reference scan",
            "reasons": reasons,
        }

    if bad_count > 0:
        reasons.append(f"{bad_count} of {entity_count} linked entities are unavailable or unknown")
        return {
            "risk": "review",
            "recommendation": "Review failed entities only; do not treat whole device as dead",
            "reasons": reasons,
        }

    return {
        "risk": "info",
        "recommendation": "No v0.1 cleanup signal",
        "reasons": ["Device has at least one healthy/current entity"],
    }
