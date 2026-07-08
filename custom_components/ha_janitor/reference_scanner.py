"""Static reference scanner for HA Janitor v0.2."""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

ENTITY_RE = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9_]+\b")

SCAN_FILE_NAMES = {
    "configuration.yaml",
    "automations.yaml",
    "scripts.yaml",
    "scenes.yaml",
    "groups.yaml",
    "ui-lovelace.yaml",
}
SCAN_DIRECTORIES = {
    "packages",
    "dashboards",
    "blueprints",
    "custom_templates",
}
STORAGE_PREFIXES = (
    "lovelace",
    "dashboard",
)
TEXT_SUFFIXES = {".yaml", ".yml", ".json", ".storage"}

# Common service/action names that look like entity IDs. This avoids flagging
# light.turn_on or homeassistant.reload_config_entry as broken entities.
SERVICE_LIKE_OBJECTS = {
    "turn_on", "turn_off", "toggle", "reload", "reload_core_config", "restart",
    "stop", "start", "set_value", "set_datetime", "set_date", "set_time",
    "select_option", "send_command", "press", "open_cover", "close_cover",
    "stop_cover", "set_cover_position", "lock", "unlock", "open_lock",
    "play_media", "media_play", "media_pause", "media_stop", "volume_set",
    "volume_up", "volume_down", "snapshot", "record", "reload_config_entry",
    "update_entity", "create", "dismiss", "persistent_notification",
}


def _source_type(path: Path, config_dir: Path) -> str:
    """Classify a scanned file."""
    rel = path.relative_to(config_dir).as_posix()
    name = path.name
    if rel.startswith(".storage/"):
        return "dashboard" if name.startswith(STORAGE_PREFIXES) else "storage"
    if name == "automations.yaml":
        return "automation"
    if name == "scripts.yaml":
        return "script"
    if name == "scenes.yaml":
        return "scene"
    if "blueprints/" in rel:
        return "blueprint"
    if "packages/" in rel:
        return "package"
    return "yaml"


def _is_service_like(candidate: str) -> bool:
    """Return true if a domain.object token is probably a service/action."""
    try:
        _domain, object_id = candidate.split(".", 1)
    except ValueError:
        return False
    return object_id in SERVICE_LIKE_OBJECTS or object_id.startswith(("turn_", "reload_", "set_"))


class ReferenceScanner:
    """Scan HA config files for entity references and likely broken references."""

    def __init__(self, hass: HomeAssistant, known_entities: set[str]) -> None:
        """Initialise scanner."""
        self.hass = hass
        self.config_dir = Path(hass.config.config_dir)
        self.known_entities = known_entities
        self.known_domains = {entity_id.split(".", 1)[0] for entity_id in known_entities if "." in entity_id}

    def scan(self) -> dict[str, Any]:
        """Return reference scan results."""
        references: dict[str, list[dict[str, Any]]] = defaultdict(list)
        broken: dict[str, list[dict[str, Any]]] = defaultdict(list)
        files_scanned: list[str] = []
        files_failed: list[dict[str, str]] = []

        for path in self._scan_paths():
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError as err:
                files_failed.append({"path": self._rel(path), "error": str(err)})
                continue

            files_scanned.append(self._rel(path))
            source_type = _source_type(path, self.config_dir)
            source_name = self._source_name(path, text)

            for line_no, line in enumerate(text.splitlines(), start=1):
                candidates = set(ENTITY_RE.findall(line))
                if not candidates:
                    continue
                for candidate in sorted(candidates):
                    domain = candidate.split(".", 1)[0]
                    if domain not in self.known_domains:
                        continue
                    if _is_service_like(candidate):
                        continue

                    ref = {
                        "target": candidate,
                        "source_type": source_type,
                        "source_name": source_name,
                        "file": self._rel(path),
                        "line": line_no,
                        "preview": line.strip()[:240],
                    }
                    if candidate in self.known_entities:
                        references[candidate].append(ref)
                    else:
                        broken[candidate].append(ref)

        return {
            "references": {key: value for key, value in references.items()},
            "broken_references": {key: value for key, value in broken.items()},
            "files_scanned": files_scanned,
            "files_failed": files_failed,
            "summary": {
                "files_scanned": len(files_scanned),
                "files_failed": len(files_failed),
                "entities_referenced": len(references),
                "broken_reference_targets": len(broken),
                "total_references": sum(len(value) for value in references.values()),
                "total_broken_references": sum(len(value) for value in broken.values()),
            },
        }

    def _scan_paths(self) -> list[Path]:
        """Return candidate paths to scan."""
        paths: list[Path] = []

        for filename in SCAN_FILE_NAMES:
            path = self.config_dir / filename
            if path.is_file():
                paths.append(path)

        for dirname in SCAN_DIRECTORIES:
            root = self.config_dir / dirname
            if root.is_dir():
                for path in root.rglob("*"):
                    if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                        paths.append(path)

        storage = self.config_dir / ".storage"
        if storage.is_dir():
            for path in storage.iterdir():
                if path.is_file() and path.name.startswith(STORAGE_PREFIXES):
                    paths.append(path)

        # Deterministic order and de-duplication.
        return sorted(set(paths), key=lambda item: item.as_posix())

    def _rel(self, path: Path) -> str:
        """Return path relative to HA config dir."""
        try:
            return path.relative_to(self.config_dir).as_posix()
        except ValueError:
            return path.as_posix()

    def _source_name(self, path: Path, text: str) -> str | None:
        """Try to derive a source name for storage/dashboard JSON."""
        if not path.as_posix().startswith((self.config_dir / ".storage").as_posix()):
            return path.name
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return path.name
        if isinstance(data, dict):
            title = data.get("title") or data.get("data", {}).get("title")
            if isinstance(title, str):
                return title
        return path.name
