# HA Janitor

Read-only Home Assistant audit helper for finding stale, unavailable, unknown, disabled and messy entities/devices.

## Status

**v0.2 is read-only.**

It does not delete, disable, hide, purge, remove, repair or mutate anything in Home Assistant.

## What v0.2 does

- Adds a Home Assistant custom integration: `ha_janitor`
- Exposes read-only WebSocket endpoints
- Audits entities, devices and integration/config entries
- Calculates current in-memory state duration
- Scans static Home Assistant config/dashboard files for entity references
- Adds reference counts to entity/device/integration rows
- Detects likely broken entity references
- Provides a Lovelace custom card with entity, device, integration and broken-reference tabs
- Supports checkbox selection and JSON export from the card

## What v0.2 deliberately does not do

- No Spook actions
- No delete actions
- No disable/hide actions
- No recorder purging
- No `.storage` mutation
- No historical duration analysis from recorder yet

## Reference scanning scope

v0.2 scans these locations under the Home Assistant config directory:

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
/local/ha-janitor-card.js?v=0.2.0
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

## v0.2 WebSocket endpoints

```text
ha_janitor/get_summary
ha_janitor/get_entities
ha_janitor/get_devices
ha_janitor/get_integrations
ha_janitor/get_references
ha_janitor/get_broken_references
```

Example browser console calls from Home Assistant frontend context:

```js
await hass.callWS({ type: "ha_janitor/get_summary" })
await hass.callWS({ type: "ha_janitor/get_broken_references", limit: 100 })
```

## Risk model

v0.2 is still intentionally conservative. Reference scanning improves confidence, but HA Janitor still does not declare anything safe to delete.

| Risk | Meaning |
|---|---|
| `protected` | Do not touch automatically |
| `review` | Needs human review |
| `info` | Informational, usually disabled/hidden/currently OK |

There is no `safe` deletion recommendation in v0.2.

## Roadmap

### v0.3

- Recorder-backed historical unavailable/unknown duration analysis
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
