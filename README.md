# HA Janitor

Read-only Home Assistant audit helper for finding stale, unavailable, unknown, disabled and messy entities/devices.

## Status

**v0.1 is audit-only.**

It does not delete, disable, hide, purge, remove, repair or mutate anything in Home Assistant.

## What v0.1 does

- Adds a Home Assistant custom integration: `ha_janitor`
- Exposes read-only WebSocket endpoints
- Audits entities, devices and integration/config entries
- Calculates basic stale-state duration
- Applies conservative risk/review scoring
- Provides a simple Lovelace custom card
- Supports checkbox selection and JSON export from the card

## What v0.1 deliberately does not do

- No Spook actions
- No delete actions
- No disable/hide actions
- No recorder purging
- No `.storage` mutation
- No automation/dashboard reference scanning yet

Reference scanning and Spook-backed safe actions are planned for later releases.

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

Restart Home Assistant.

Then go to:

```text
Settings → Devices & services → Add integration → HA Janitor
```

## Add the card to a dashboard

Add this JavaScript module as a dashboard resource:

```text
/local/ha-janitor-card.js
```

Resource type:

```text
JavaScript module
```

Then add a manual card:

```yaml
type: custom:ha-janitor-card
title: HA Janitor
show_limit: 250
```

## v0.1 WebSocket endpoints

```text
ha_janitor/get_summary
ha_janitor/get_entities
ha_janitor/get_devices
ha_janitor/get_integrations
```

Example browser console call from Home Assistant frontend context:

```js
await hass.callWS({ type: "ha_janitor/get_summary" })
```

## Risk model in v0.1

v0.1 is intentionally conservative because it does not yet scan automations, scripts, scenes or dashboards.

| Risk | Meaning |
|---|---|
| `protected` | Do not touch automatically |
| `review` | Needs human review |
| `info` | Informational, usually disabled/hidden/currently OK |

There is no `safe` deletion recommendation in v0.1.

## Roadmap

### v0.2

- YAML reference scanner
- Dashboard reference scanner
- Broken entity/action references
- Better risk scoring

### v0.3

- Review state store
- Keep / ignore / reviewed flags
- CSV export

### v0.4

- Optional Spook adapter
- Safe actions only: hide/unhide, disable/enable

### v1.0

- HACS-ready release
- Tests
- Documentation
- Safer workflows around cleanup queues
