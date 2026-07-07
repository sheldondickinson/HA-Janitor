"""Config flow for HA Janitor."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries

from .const import DOMAIN, NAME


class HAJanitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an HA Janitor config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title=NAME, data={})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            errors={},
        )
