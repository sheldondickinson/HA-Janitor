# HA Janitor

Read-only Home Assistant audit helper for finding stale, unavailable, unknown, disabled and messy entities/devices.

## Status

**v0.4 is read-only.**

It does not delete, disable, hide, purge, remove, repair or mutate anything in Home Assistant.

## What v0.4 does

- Adds a Home Assistant custom integration: `ha_janitor`
- Exposes read-only WebSocket endpoints
- Audits entities, devices and integration/config entries
- Calculates current in-memory state duration
- Adds read-only SQLite recorder-backed unavailable/unknown streak analysis
- Scans static Home Assistant config/dashboard files for entity references
- Adds reference counts to entity/device/integration rows
- Detects likely broken entity references
- Adds persistent review states using Home Assistant storage
- Supports review dispositions: reviewed, keep, ignore, candidate disable, candidate delete later, do not touch
- Adds review-state filters and review summary cards
- Adds CSV export and JSON export
- Provides a Lovelace custom card with entity, device, integration and broken-reference tabs
- Debounces search input so filtering waits briefly after typing

## What v0.4 deliberately does not do

- No Spook actions
- No delete actions
- No disable/hide actions
- No recorder purging
- No `.storage` mutation
- No direct database writes
- No support yet for non-SQLite recorder databases

## Recorder analysis

v0.4 opens the default Home Assistant SQLite recorder database read-only:

```text
/config/home-assistant_v2.db
```

It attempts to calculate, for currently `unavailable` or `unknown` entities:

```text
recorder_bad_streak_days
recorder_bad_streak_start
recorder_last_healthy_state
recorder_last_healthy_at
recorder_rows_examined
```

If the database is missing, locked, external, or using an unsupported schema, HA Janitor degrades cleanly and continues with live state duration only.

## Reference scanning scope

v0.4 scans these locations under the Home Assistant config directory:

```text
configuration.yaml
automations.yaml
scripts.yaml
scenes.yaml
groups.yaml
ui-lovelace.yaml
packages/**/*.yaml
packages/**/*.yml
dashboards/**/*.yaml
dashboards/**/*.yml
blueprints/**/*.yaml
blueprints/**/*.yml
custom_templates/**/*.yaml
custom_templates/**/*.yml
.storage/lovelace*
.storage/dashboard*
```

The scanner is static text-based. It is useful, but not perfect. False positives are possible where service/action names look like entity IDs.

## Review state

Review state is stored in Home Assistant storage under:

```text
.storage/ha_janitor.review_state
```

Do not edit that file directly.

Supported dispositions:

```text
unreviewed
reviewed
keep
ignore
candidate_disable
candidate_delete_later
do_not_touch
```

## Installation for development

From your Home Assistant config directory:

```bash
git clone https://github.com/sheldondickinson/HA-Janitor.git
```

Then copy or symlink:

```bash
cp -R HA-Janitor/custom_components/ha_janitor custom_components/ha_janitor
cp HA-Janitor/www/ha-janitor-card.js www/ha-janitor-card.js
```

Restart Home Assistant after backend integration changes.

Then go to:

```text
Settings → Devices & services → Add integration → HA Janitor
```

## Add the card to a dashboard

Add this JavaScript module as a dashboard resource:

```text
/local/ha-janitor-card.js?v=0.4.0
```

Resource type:

```text
JavaScript module
```

Then add a manual card:

```yaml
type: custom:ha-janitor-card
title: HA Janitor
show_limit: 500
```

## v0.4 WebSocket endpoints

```text
ha_janitor/get_summary
ha_janitor/get_entities
ha_janitor/get_devices
ha_janitor/get_integrations
ha_janitor/get_references
ha_janitor/get_broken_references
ha_janitor/get_review_state
ha_janitor/set_entity_review
ha_janitor/clear_entity_review
ha_janitor/export_entities_csv
```

Example browser console calls from Home Assistant frontend context:

```js
await hass.callWS({ type: "ha_janitor/get_summary" })
await hass.callWS({ type: "ha_janitor/get_broken_references", limit: 100 })
await hass.callWS({ type: "ha_janitor/set_entity_review", entity_id: "sensor.example", disposition: "keep", note: "Deliberately retained" })
```

## Risk model

v0.4 is still intentionally conservative. Reference scanning, review state and recorder duration improve workflow, but HA Janitor still does not declare anything safe to delete.

| Risk | Meaning |
|---|---|
| `protected` | Do not touch automatically |
| `review` | Needs human review |
| `info` | Informational, usually disabled/hidden/currently OK |

There is no `safe` deletion recommendation in v0.4.

## Roadmap

### v0.5

- Optional Spook adapter
- Safe actions only: hide/unhide, disable/enable

### v1.0

- HACS-ready release
- Tests
- Documentation
- Safer workflows around cleanup queues
