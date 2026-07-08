"""Read-only SQLite recorder duration analysis for HA Janitor.

This module is intentionally conservative. It only supports the default
SQLite recorder database for now and opens it read-only. If the database is
not available, locked or not using a supported schema, it degrades cleanly.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

BAD_STATES = {STATE_UNAVAILABLE, STATE_UNKNOWN}
DEFAULT_DB_NAME = "home-assistant_v2.db"
MAX_ROWS_PER_ENTITY = 5000


def _iso_from_ts(value: float | int | None) -> str | None:
    """Convert a unix timestamp to ISO format."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _days_since(value: float | int | None) -> float | None:
    """Return days since unix timestamp."""
    if value is None:
        return None
    try:
        return round((datetime.now(timezone.utc).timestamp() - float(value)) / 86400, 2)
    except (TypeError, ValueError):
        return None


class RecorderAnalyser:
    """Read-only SQLite-backed recorder analyser."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise analyser."""
        self.hass = hass
        self.db_path = Path(hass.config.config_dir) / DEFAULT_DB_NAME
        self.available = False
        self.status = "not_started"
        self.schema = "unknown"
        self.error: str | None = None

    def analyse(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Annotate rows with recorder history and return summary."""
        bad_rows = [row for row in rows if row.get("state") in BAD_STATES]
        for row in rows:
            row.setdefault("recorder_supported", False)
            row.setdefault("recorder_bad_streak_days", None)
            row.setdefault("recorder_bad_streak_start", None)
            row.setdefault("recorder_bad_streak_is_capped", False)
            row.setdefault("recorder_bad_streak_basis", "none")
            row.setdefault("recorder_last_healthy_state", None)
            row.setdefault("recorder_last_healthy_at", None)
            row.setdefault("recorder_oldest_state_at", None)
            row.setdefault("recorder_rows_examined", 0)

        if not self.db_path.exists():
            self.status = "sqlite_db_not_found"
            return self._summary(rows, bad_rows)

        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=2.0)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as err:
            self.status = "sqlite_open_failed"
            self.error = str(err)
            return self._summary(rows, bad_rows)

        try:
            schema = self._detect_schema(conn)
            self.schema = schema
            if schema == "unsupported":
                self.status = "unsupported_schema"
                return self._summary(rows, bad_rows)

            self.available = True
            self.status = "ok"
            for row in bad_rows:
                entity_id = row.get("entity_id")
                if not entity_id:
                    continue
                history = self._analyse_entity(conn, schema, entity_id)
                row.update(history)
        except sqlite3.Error as err:
            self.status = "sqlite_query_failed"
            self.error = str(err)
        finally:
            conn.close()

        return self._summary(rows, bad_rows)

    def _detect_schema(self, conn: sqlite3.Connection) -> str:
        """Detect supported recorder schema."""
        columns = self._columns(conn, "states")
        if not columns:
            return "unsupported"
        if {"metadata_id", "state"}.issubset(columns) and "states_meta" in self._tables(conn):
            return "modern"
        if {"entity_id", "state"}.issubset(columns):
            return "legacy"
        return "unsupported"

    def _tables(self, conn: sqlite3.Connection) -> set[str]:
        """Return table names."""
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    def _columns(self, conn: sqlite3.Connection, table: str) -> set[str]:
        """Return column names for a table."""
        try:
            return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        except sqlite3.Error:
            return set()

    def _time_column(self, conn: sqlite3.Connection) -> str:
        """Return best available timestamp column expression."""
        cols = self._columns(conn, "states")
        if "last_updated_ts" in cols:
            return "last_updated_ts"
        if "last_changed_ts" in cols:
            return "last_changed_ts"
        if "last_updated" in cols:
            return "strftime('%s', last_updated)"
        if "last_changed" in cols:
            return "strftime('%s', last_changed)"
        return "NULL"

    def _analyse_entity(self, conn: sqlite3.Connection, schema: str, entity_id: str) -> dict[str, Any]:
        """Analyse the bad-state streak for one entity.

        If no healthy state is found in the recorder window, the result is a
        lower bound, not an exact duration. Example: >= 9.56 days.
        """
        time_col = self._time_column(conn)
        if schema == "modern":
            query = f"""
                SELECT s.state AS state, {time_col} AS ts
                FROM states AS s
                JOIN states_meta AS sm ON sm.metadata_id = s.metadata_id
                WHERE sm.entity_id = ? AND s.state IS NOT NULL
                ORDER BY ts DESC
                LIMIT ?
            """
        else:
            query = f"""
                SELECT state AS state, {time_col} AS ts
                FROM states
                WHERE entity_id = ? AND state IS NOT NULL
                ORDER BY ts DESC
                LIMIT ?
            """

        rows = list(conn.execute(query, (entity_id, MAX_ROWS_PER_ENTITY)))
        result: dict[str, Any] = {
            "recorder_supported": True,
            "recorder_rows_examined": len(rows),
            "recorder_bad_streak_days": None,
            "recorder_bad_streak_start": None,
            "recorder_bad_streak_is_capped": False,
            "recorder_bad_streak_basis": "none",
            "recorder_last_healthy_state": None,
            "recorder_last_healthy_at": None,
            "recorder_oldest_state_at": None,
        }
        if not rows:
            return result

        bad_start_ts: float | None = None
        last_healthy_state: str | None = None
        last_healthy_ts: float | None = None
        oldest_ts: float | None = None

        for db_row in rows:
            state = db_row["state"]
            ts = db_row["ts"]
            try:
                ts_float = float(ts) if ts is not None else None
            except (TypeError, ValueError):
                ts_float = None

            if ts_float is not None:
                oldest_ts = ts_float

            if state in BAD_STATES:
                if ts_float is not None:
                    bad_start_ts = ts_float
                continue

            last_healthy_state = state
            last_healthy_ts = ts_float
            break

        result["recorder_last_healthy_state"] = last_healthy_state
        result["recorder_last_healthy_at"] = _iso_from_ts(last_healthy_ts)
        result["recorder_oldest_state_at"] = _iso_from_ts(oldest_ts)

        if bad_start_ts is None:
            return result

        result["recorder_bad_streak_start"] = _iso_from_ts(bad_start_ts)
        result["recorder_bad_streak_days"] = _days_since(bad_start_ts)

        if last_healthy_state is None:
            result["recorder_bad_streak_is_capped"] = True
            result["recorder_bad_streak_basis"] = "lower_bound_no_healthy_state_in_retention_window"
        else:
            result["recorder_bad_streak_basis"] = "exact_last_healthy_state_found"

        return result

    def _summary(self, rows: list[dict[str, Any]], bad_rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Return recorder analysis summary."""
        annotated = [row for row in rows if row.get("recorder_bad_streak_days") is not None]
        capped = [row for row in rows if row.get("recorder_bad_streak_is_capped")]
        return {
            "recorder_status": self.status,
            "recorder_available": self.available,
            "recorder_schema": self.schema,
            "recorder_error": self.error,
            "recorder_db_path": str(self.db_path),
            "recorder_bad_entities_checked": len(bad_rows),
            "recorder_entities_annotated": len(annotated),
            "recorder_entities_capped": len(capped),
            "recorder_note": "Capped values are lower bounds caused by recorder retention/no healthy state found.",
        }
