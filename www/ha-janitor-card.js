class HaJanitorCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {};
    this._loaded = false;
    this._loading = false;
    this._error = null;
    this._summary = null;
    this._entities = [];
    this._devices = [];
    this._integrations = [];
    this._brokenReferences = [];
    this._selected = new Set();
    this._view = "entities";
    this._filters = { search: "", state: "bad", risk: "all", integration: "all", minDays: "0", references: "all" };
  }

  setConfig(config) { this._config = { title: "HA Janitor", show_limit: 250, ...config }; this._render(); }
  set hass(hass) { this._hass = hass; if (!this._loaded && !this._loading) this._load(); }
  getCardSize() { return 10; }

  async _load() {
    if (!this._hass) return;
    this._loading = true; this._error = null; this._render();
    try {
      const limit = this._config.show_limit || 250;
      const [summary, entities, devices, integrations, brokenReferences] = await Promise.all([
        this._hass.callWS({ type: "ha_janitor/get_summary" }),
        this._hass.callWS({ type: "ha_janitor/get_entities", limit }),
        this._hass.callWS({ type: "ha_janitor/get_devices", limit }),
        this._hass.callWS({ type: "ha_janitor/get_integrations", limit }),
        this._hass.callWS({ type: "ha_janitor/get_broken_references", limit: 500 })
      ]);
      this._summary = summary; this._entities = entities || []; this._devices = devices || []; this._integrations = integrations || []; this._brokenReferences = brokenReferences || []; this._loaded = true;
    } catch (err) { this._error = err && err.message ? err.message : String(err); }
    finally { this._loading = false; this._render(); }
  }

  _filteredEntities() {
    const search = this._filters.search.toLowerCase().trim(); const minDays = Number(this._filters.minDays || 0);
    return this._entities.filter((entity) => {
      const refCount = Number(entity.reference_count || 0);
      if (this._filters.state === "bad" && !["unavailable", "unknown"].includes(entity.state)) return false;
      if (this._filters.state !== "all" && this._filters.state !== "bad" && entity.state !== this._filters.state) return false;
      if (this._filters.risk !== "all" && entity.risk !== this._filters.risk) return false;
      if (this._filters.integration !== "all" && entity.integration_domain !== this._filters.integration) return false;
      if (this._filters.references === "referenced" && refCount === 0) return false;
      if (this._filters.references === "unreferenced" && refCount > 0) return false;
      if ((entity.duration_current_state_days || 0) < minDays) return false;
      if (search) {
        const haystack = [entity.entity_id, entity.name, entity.device_name, entity.area_name, entity.integration_domain, entity.state, entity.risk, entity.recommendation]
          .filter(Boolean).join(" ").toLowerCase();
        if (!haystack.includes(search)) return false;
      }
      return true;
    });
  }

  _integrationOptions() { return Array.from(new Set(this._entities.map((entity) => entity.integration_domain).filter(Boolean))).sort(); }
  _toggleEntity(entityId, checked) { if (checked) this._selected.add(entityId); else this._selected.delete(entityId); this._render(); }
  _selectVisible() { for (const entity of this._filteredEntities()) this._selected.add(entity.entity_id); this._render(); }
  _clearSelection() { this._selected.clear(); this._render(); }

  _exportJson() {
    const payload = { exported_at: new Date().toISOString(), tool: "HA Janitor", version: "0.2.0", note: "v0.2 is read-only. Export is for manual review only.", summary: this._summary, selected_entities: this._entities.filter((entity) => this._selected.has(entity.entity_id)), broken_references: this._brokenReferences };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = "ha-janitor-export.json"; link.click(); URL.revokeObjectURL(url);
  }

  _riskClass(risk) { return `risk risk-${risk || "info"}`; }
  _stateClass(state) { if (state === "unavailable") return "state state-bad"; if (state === "unknown") return "state state-warn"; return "state"; }
  _formatDuration(entity) { const seconds = Number(entity.duration_current_state_seconds); if (!Number.isFinite(seconds)) return "–"; if (seconds < 60) return "<1 min"; const minutes = Math.floor(seconds / 60); if (minutes < 60) return `${minutes} min`; const hours = Math.floor(minutes / 60); const remainingMinutes = minutes % 60; if (hours < 24) return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`; const days = Math.floor(hours / 24); const remainingHours = hours % 24; return remainingHours > 0 ? `${days}d ${remainingHours}h` : `${days}d`; }

  _renderSummary() {
    const s = this._summary || {};
    const cards = [
      ["Entities", s.entities_total], ["Devices", s.devices_total], ["Integrations", s.integrations_total], ["Unavailable", s.entities_unavailable], ["Unknown", s.entities_unknown], ["Referenced", s.entities_referenced], ["Unreferenced", s.entities_unreferenced], ["Broken refs", s.broken_reference_targets], ["Files scanned", s.files_scanned]
    ];
    return `<div class="summary-grid">${cards.map(([label, value]) => `<div class="summary-card"><div class="summary-value">${value ?? "–"}</div><div class="summary-label">${label}</div></div>`).join("")}</div><div class="notice">v0.2 is read-only. Static reference scanning is enabled. Durations still reset after HA restart until recorder analysis is added.</div>`;
  }

  _renderTabs() { const tabs = [["entities", "Entities"], ["devices", "Devices"], ["integrations", "Integrations"], ["broken", `Broken refs (${this._brokenReferences.length})`]]; return `<div class="tabs">${tabs.map(([key, label]) => `<button class="tab ${this._view === key ? "active" : ""}" data-view="${key}">${label}</button>`).join("")}</div>`; }

  _renderFilters() {
    const integrations = this._integrationOptions();
    return `<div class="filters">
      <input id="search" placeholder="Search entity, device, area, integration…" value="${this._escape(this._filters.search)}" />
      <select id="stateFilter">${this._option("bad", "Unavailable or unknown", this._filters.state)}${this._option("all", "Any state", this._filters.state)}${this._option("unavailable", "Unavailable", this._filters.state)}${this._option("unknown", "Unknown", this._filters.state)}</select>
      <select id="riskFilter">${this._option("all", "Any risk", this._filters.risk)}${this._option("review", "Review", this._filters.risk)}${this._option("protected", "Protected", this._filters.risk)}${this._option("info", "Info", this._filters.risk)}</select>
      <select id="integrationFilter">${this._option("all", "Any integration", this._filters.integration)}${integrations.map((value) => this._option(value, value, this._filters.integration)).join("")}</select>
      <select id="referenceFilter">${this._option("all", "Any reference state", this._filters.references)}${this._option("referenced", "Referenced", this._filters.references)}${this._option("unreferenced", "Unreferenced", this._filters.references)}</select>
      <select id="daysFilter">${this._option("0", "Any duration", this._filters.minDays)}${this._option("1", "1+ day", this._filters.minDays)}${this._option("7", "7+ days", this._filters.minDays)}${this._option("30", "30+ days", this._filters.minDays)}${this._option("90", "90+ days", this._filters.minDays)}</select>
    </div><div class="actions"><button id="refresh">Refresh</button><button id="selectVisible">Select visible</button><button id="clearSelection">Clear selection</button><button id="exportJson" ${this._selected.size === 0 ? "disabled" : ""}>Export selected JSON</button><span class="selected">${this._selected.size} selected</span></div>`;
  }

  _renderEntityTable() {
    const rows = this._filteredEntities();
    return `${this._renderFilters()}<div class="table-wrap entity-table-wrap"><table class="entity-table"><thead><tr><th class="select-col">Select</th><th>Risk</th><th>Entity</th><th>State</th><th>Duration</th><th>Refs</th><th>Device</th><th>Area</th><th>Integration</th><th class="recommendation-col">Recommendation</th></tr></thead><tbody>${rows.map((entity) => {
      const references = entity.references || []; const refTitle = references.map((ref) => `${ref.file}:${ref.line}`).join("\n");
      return `<tr><td class="select-cell"><input type="checkbox" class="rowSelect" aria-label="Select ${this._escape(entity.entity_id)}" data-entity="${this._escape(entity.entity_id)}" ${this._selected.has(entity.entity_id) ? "checked" : ""}></td><td><span class="${this._riskClass(entity.risk)}">${this._escape(entity.risk)}</span></td><td class="entity-cell"><div class="primary">${this._escape(entity.entity_id)}</div><div class="secondary">${this._escape(entity.name || "")}</div></td><td><span class="${this._stateClass(entity.state)}">${this._escape(entity.state ?? "no state")}</span></td><td class="duration-cell">${this._formatDuration(entity)}</td><td class="refs-cell" title="${this._escape(refTitle)}">${Number(entity.reference_count || 0)}</td><td>${this._escape(entity.device_name || "–")}</td><td>${this._escape(entity.area_name || "–")}</td><td>${this._escape(entity.integration_domain || "–")}</td><td class="recommendation-cell"><div>${this._escape(entity.recommendation || "")}</div><div class="secondary">${this._escape((entity.reasons || []).join("; "))}</div></td></tr>`;
    }).join("")}</tbody></table></div><div class="footer-note">Showing ${rows.length} entity rows. Limit is ${this._config.show_limit || 250}. References scan YAML, packages, dashboards, blueprints and selected .storage Lovelace files.</div>`;
  }

  _renderDeviceTable() {
    return `<div class="table-wrap"><table><thead><tr><th>Risk</th><th>Device</th><th>Area</th><th>Integrations</th><th>Entities</th><th>Unavailable</th><th>Unknown</th><th>Healthy</th><th>Refs</th><th>Recommendation</th></tr></thead><tbody>${this._devices.map((device) => `<tr><td><span class="${this._riskClass(device.risk)}">${this._escape(device.risk)}</span></td><td><div class="primary">${this._escape(device.name || device.device_id)}</div><div class="secondary">${this._escape([device.manufacturer, device.model].filter(Boolean).join(" / "))}</div></td><td>${this._escape(device.area_name || "–")}</td><td>${this._escape((device.integration_domains || []).join(", ") || "–")}</td><td>${device.entity_count}</td><td>${device.unavailable_entity_count}</td><td>${device.unknown_entity_count}</td><td>${device.healthy_entity_count}</td><td>${device.reference_count || 0}</td><td><div>${this._escape(device.recommendation || "")}</div><div class="secondary">${this._escape((device.reasons || []).join("; "))}</div></td></tr>`).join("")}</tbody></table></div>`;
  }

  _renderIntegrationTable() { return `<div class="table-wrap"><table><thead><tr><th>Domain</th><th>Title</th><th>State</th><th>Devices</th><th>Entities</th><th>Unavailable</th><th>Unknown</th><th>Referenced entities</th><th>Refs</th></tr></thead><tbody>${this._integrations.map((entry) => `<tr><td>${this._escape(entry.domain)}</td><td>${this._escape(entry.title)}</td><td><span class="state">${this._escape(entry.state)}</span></td><td>${entry.device_count}</td><td>${entry.entity_count}</td><td>${entry.unavailable_count}</td><td>${entry.unknown_count}</td><td>${entry.referenced_entity_count || 0}</td><td>${entry.reference_count || 0}</td></tr>`).join("")}</tbody></table></div>`; }

  _renderBrokenReferences() {
    return `<div class="table-wrap"><table><thead><tr><th>Missing target</th><th>Count</th><th>First locations</th></tr></thead><tbody>${this._brokenReferences.map((item) => `<tr><td><div class="primary">${this._escape(item.target)}</div></td><td>${item.reference_count}</td><td>${(item.references || []).slice(0, 5).map((ref) => `<div><strong>${this._escape(ref.file)}:${ref.line}</strong> <span class="secondary">${this._escape(ref.preview || "")}</span></div>`).join("")}</td></tr>`).join("")}</tbody></table></div><div class="footer-note">Broken references are likely stale entity IDs in YAML or dashboard storage. False positives are possible where service/action names look like entity IDs.</div>`;
  }

  _option(value, label, selected) { return `<option value="${this._escape(value)}" ${value === selected ? "selected" : ""}>${this._escape(label)}</option>`; }
  _escape(value) { return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;"); }

  _render() {
    if (!this.shadowRoot) return; let body = "";
    if (this._loading) body = `<div class="loading">Loading HA Janitor audit and reference scan…</div>`;
    else if (this._error) body = `<div class="error">${this._escape(this._error)}</div>`;
    else if (!this._loaded) body = `<div class="loading">Waiting for Home Assistant…</div>`;
    else { const view = this._view === "devices" ? this._renderDeviceTable() : this._view === "integrations" ? this._renderIntegrationTable() : this._view === "broken" ? this._renderBrokenReferences() : this._renderEntityTable(); body = `${this._renderSummary()}${this._renderTabs()}${view}`; }
    this.shadowRoot.innerHTML = `<ha-card><div class="card"><div class="header"><div><h2>${this._escape(this._config.title || "HA Janitor")}</h2><div class="subtitle">Read-only v0.2.0 audit dashboard</div></div></div>${body}</div></ha-card><style>
      :host{display:block}.card{padding:16px}.header{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}h2{margin:0;font-size:22px;font-weight:600}.subtitle,.secondary,.footer-note{color:var(--secondary-text-color);font-size:12px}.summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px;margin:16px 0 8px}.summary-card{border:1px solid var(--divider-color);border-radius:10px;padding:10px;background:var(--card-background-color)}.summary-value{font-size:22px;font-weight:700}.summary-label{color:var(--secondary-text-color);font-size:12px}.notice{margin:10px 0 14px;padding:10px 12px;border-radius:8px;background:rgba(255,193,7,.12);color:var(--primary-text-color);font-size:13px}.tabs{display:flex;gap:8px;margin:12px 0;flex-wrap:wrap}.tab,button{border:1px solid var(--divider-color);border-radius:8px;padding:7px 10px;background:var(--card-background-color);color:var(--primary-text-color);cursor:pointer}.tab.active{background:var(--primary-color);color:var(--text-primary-color);border-color:var(--primary-color)}.filters{display:grid;grid-template-columns:2fr repeat(5,minmax(120px,1fr));gap:8px;margin:12px 0}input,select{width:100%;box-sizing:border-box;border:1px solid var(--divider-color);border-radius:8px;padding:8px;background:var(--card-background-color);color:var(--primary-text-color)}.actions{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:8px 0 12px}button:disabled{opacity:.5;cursor:not-allowed}.selected{color:var(--secondary-text-color);font-size:13px}.table-wrap{overflow-x:auto;border:1px solid var(--divider-color);border-radius:10px}table{width:100%;border-collapse:collapse;font-size:13px;table-layout:auto}th,td{padding:9px 8px;border-bottom:1px solid var(--divider-color);text-align:left;vertical-align:top}th{font-weight:600;color:var(--secondary-text-color);white-space:nowrap}tr:last-child td{border-bottom:0}.select-col,.select-cell{width:64px;min-width:64px;text-align:center;vertical-align:top}.select-cell{padding-top:11px}input.rowSelect{appearance:auto;width:22px;height:22px;min-width:22px;margin:0;cursor:pointer;accent-color:var(--primary-color)}.entity-cell{min-width:280px}.duration-cell,.refs-cell{white-space:nowrap}.refs-cell{font-weight:700}.recommendation-col,.recommendation-cell{min-width:260px;max-width:420px}.recommendation-cell{line-height:1.35}.primary{font-weight:600;white-space:nowrap}.risk,.state{display:inline-block;border-radius:999px;padding:2px 8px;font-size:12px;border:1px solid var(--divider-color);white-space:nowrap}.risk-review{background:rgba(255,193,7,.14)}.risk-protected{background:rgba(244,67,54,.14)}.risk-info{background:rgba(33,150,243,.10)}.state-bad{background:rgba(244,67,54,.14)}.state-warn{background:rgba(255,193,7,.14)}.loading,.error{padding:16px;border-radius:8px;border:1px solid var(--divider-color);margin-top:12px}.error{background:rgba(244,67,54,.12)}code{font-family:var(--code-font-family,monospace)}@media(max-width:1100px){.filters{grid-template-columns:1fr}}
    </style>`; this._bindEvents();
  }

  _bindEvents() {
    const root = this.shadowRoot; if (!root) return;
    root.querySelectorAll(".tab").forEach((button) => button.addEventListener("click", () => { this._view = button.dataset.view; this._render(); }));
    const bindChange = (id, key) => { const el = root.getElementById(id); if (el) el.addEventListener("change", (event) => { this._filters[key] = event.target.value; this._render(); }); };
    const search = root.getElementById("search"); if (search) search.addEventListener("input", (event) => { this._filters.search = event.target.value; this._render(); });
    bindChange("stateFilter", "state"); bindChange("riskFilter", "risk"); bindChange("integrationFilter", "integration"); bindChange("daysFilter", "minDays"); bindChange("referenceFilter", "references");
    const refresh = root.getElementById("refresh"); if (refresh) refresh.addEventListener("click", () => { this._loaded = false; this._load(); });
    const selectVisible = root.getElementById("selectVisible"); if (selectVisible) selectVisible.addEventListener("click", () => this._selectVisible());
    const clearSelection = root.getElementById("clearSelection"); if (clearSelection) clearSelection.addEventListener("click", () => this._clearSelection());
    const exportJson = root.getElementById("exportJson"); if (exportJson) exportJson.addEventListener("click", () => this._exportJson());
    root.querySelectorAll(".rowSelect").forEach((input) => input.addEventListener("change", (event) => this._toggleEntity(event.target.dataset.entity, event.target.checked)));
  }
}

customElements.define("ha-janitor-card", HaJanitorCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: "ha-janitor-card", name: "HA Janitor", description: "Read-only audit dashboard for stale Home Assistant entities and broken references." });
