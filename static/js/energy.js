/**
 * Energy AI Controller – frontend JavaScript
 * Manages BESS, solar farm, Bitcoin mining rig, and cooling zone data
 * via the Flask REST API and drives the AI analysis / execution workflow.
 */

(() => {
  "use strict";

  // ── State ────────────────────────────────────────────────────────────────

  let pendingRecs = [];   // Current AI recommendation list

  // ── DOM refs ─────────────────────────────────────────────────────────────

  const statSolar    = document.getElementById("statSolar");
  const statBess     = document.getElementById("statBess");
  const statHashRate = document.getElementById("statHashRate");
  const statNetPower = document.getElementById("statNetPower");
  const statAlerts   = document.getElementById("statAlerts");

  const alertsBanner         = document.getElementById("alertsBanner");
  const solarList            = document.getElementById("solarList");
  const bessList             = document.getElementById("bessList");
  const rigList              = document.getElementById("rigList");
  const zoneList             = document.getElementById("zoneList");
  const recommendationsPanel = document.getElementById("recommendationsPanel");
  const actionLog            = document.getElementById("actionLog");
  const actionLogCount       = document.getElementById("actionLogCount");

  const btnRefresh   = document.getElementById("btnRefresh");
  const btnAnalyze   = document.getElementById("btnAnalyze");
  const btnSelectAll = document.getElementById("btnSelectAll");
  const btnExecute   = document.getElementById("btnExecute");

  const toast = document.getElementById("toast");

  // ── Toast ────────────────────────────────────────────────────────────────

  let toastTimer = null;

  function showToast(message, type = "success") {
    toast.textContent  = message;
    toast.className    = `toast toast--${type}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.classList.add("hidden"); }, 3500);
  }

  // ── API helpers ──────────────────────────────────────────────────────────

  async function apiFetch(url, options = {}) {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ description: "Request failed" }));
      throw new Error(err.description || `HTTP ${res.status}`);
    }
    return res.json();
  }

  // ── Utility ──────────────────────────────────────────────────────────────

  function esc(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function fmt(val, decimals = 1) {
    if (val == null) return "–";
    return Number(val).toFixed(decimals);
  }

  function fmtDate(iso) {
    if (!iso) return "–";
    return new Date(iso).toLocaleString();
  }

  function pill(text, type) {
    return `<span class="pill pill--${esc(type)}">${esc(text)}</span>`;
  }

  function progressBar(pct, theme) {
    const w = Math.min(100, Math.max(0, pct || 0));
    return `
      <div class="progress-wrap">
        <div class="progress-bar progress-bar--${esc(theme)}" style="width:${w}%"></div>
      </div>`;
  }

  // ── Modals ────────────────────────────────────────────────────────────────

  function openModal(id) {
    document.getElementById(id).classList.remove("hidden");
  }

  function closeModal(id) {
    document.getElementById(id).classList.add("hidden");
  }

  // Wire close buttons (data-close attribute)
  document.querySelectorAll("[data-close]").forEach((btn) => {
    btn.addEventListener("click", () => closeModal(btn.dataset.close));
  });

  // Close on backdrop click
  document.querySelectorAll(".modal-backdrop").forEach((backdrop) => {
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) backdrop.classList.add("hidden");
    });
  });

  // Escape key closes all
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      document.querySelectorAll(".modal-backdrop").forEach((m) => m.classList.add("hidden"));
    }
  });

  // ── Status overview ──────────────────────────────────────────────────────

  async function loadStatus() {
    try {
      const d = await apiFetch("/api/energy/status");

      statSolar.textContent    = `${fmt(d.solar.current_output_kw)} kW`;
      statBess.textContent     = `${fmt(d.bess.avg_soc_pct)} %`;
      statHashRate.textContent = `${fmt(d.mining.total_hash_rate_ths, 2)} TH/s`;

      const net = d.net_power_kw;
      statNetPower.textContent = `${net >= 0 ? "+" : ""}${fmt(net)} kW`;
      statNetPower.style.color = net >= 0
        ? "var(--color-accent)"
        : "var(--color-danger)";

      const alertCount = d.alerts.length;
      statAlerts.textContent = alertCount;
      statAlerts.style.color = alertCount > 0
        ? "var(--color-danger)"
        : "var(--color-text-muted)";

      // Alerts banner
      if (alertCount > 0) {
        alertsBanner.innerHTML = d.alerts.map((a) =>
          `<div class="alert-item alert-item--${esc(a.severity)}">
            ⚠ ${esc(a.message)}
           </div>`
        ).join("");
        alertsBanner.classList.remove("hidden");
      } else {
        alertsBanner.classList.add("hidden");
      }
    } catch (e) {
      console.error("Failed to load status:", e);
    }
  }

  // ── Solar Farms ──────────────────────────────────────────────────────────

  async function loadSolar() {
    try {
      const farms = await apiFetch("/api/solar");
      if (farms.length === 0) {
        solarList.innerHTML = "<p class='empty-state'>No solar farms configured.</p>";
        return;
      }
      solarList.innerHTML = farms.map((f) => `
        <div class="device-card ${f.is_active ? "" : "device-card--inactive"}">
          <div class="device-card__header">
            <span class="device-card__name">☀ ${esc(f.name)}</span>
            <div class="device-card__actions">
              <button class="btn btn--sm btn--icon" onclick="editSolar(${f.id})" title="Edit">✏️</button>
              <button class="btn btn--sm btn--danger" onclick="deleteSolar(${f.id},'${esc(f.name)}')" title="Delete">🗑</button>
            </div>
          </div>
          <div class="device-card__metrics">
            <div class="metric">
              <span class="metric__label">Output</span>
              <span class="metric__value" style="color:var(--color-solar)">${fmt(f.current_output_kw)} kW</span>
            </div>
            <div class="metric">
              <span class="metric__label">Capacity</span>
              <span class="metric__value">${fmt(f.capacity_kw)} kW</span>
            </div>
            <div class="metric">
              <span class="metric__label">Irradiance</span>
              <span class="metric__value">${fmt(f.irradiance_wm2, 0)} W/m²</span>
            </div>
            <div class="metric">
              <span class="metric__label">Efficiency</span>
              <span class="metric__value">${fmt(f.efficiency_pct)} %</span>
            </div>
          </div>
          ${progressBar(f.utilization_pct, "solar")}
          <div style="font-size:.72rem;color:var(--color-text-muted)">${fmt(f.utilization_pct)} % utilisation</div>
          ${f.location ? `<div style="font-size:.75rem;color:var(--color-text-muted)">📍 ${esc(f.location)}</div>` : ""}
          ${pill(f.is_active ? "Active" : "Inactive", f.is_active ? "active" : "inactive")}
        </div>
      `).join("");
    } catch (e) {
      showToast("Failed to load solar farms: " + e.message, "error");
    }
  }

  // ── BESS Units ───────────────────────────────────────────────────────────

  async function loadBess() {
    try {
      const units = await apiFetch("/api/bess");
      if (units.length === 0) {
        bessList.innerHTML = "<p class='empty-state'>No BESS units configured.</p>";
        return;
      }
      bessList.innerHTML = units.map((b) => `
        <div class="device-card ${b.is_active ? "" : "device-card--inactive"}">
          <div class="device-card__header">
            <span class="device-card__name">🔋 ${esc(b.name)}</span>
            <div class="device-card__actions">
              <button class="btn btn--sm btn--icon" onclick="editBess(${b.id})" title="Edit">✏️</button>
              <button class="btn btn--sm btn--danger" onclick="deleteBess(${b.id},'${esc(b.name)}')" title="Delete">🗑</button>
            </div>
          </div>
          <div class="device-card__metrics">
            <div class="metric">
              <span class="metric__label">SOC</span>
              <span class="metric__value" style="color:var(--color-bess)">${fmt(b.state_of_charge_pct)} %</span>
            </div>
            <div class="metric">
              <span class="metric__label">Stored</span>
              <span class="metric__value">${fmt(b.stored_energy_kwh, 0)} kWh</span>
            </div>
            <div class="metric">
              <span class="metric__label">Power</span>
              <span class="metric__value">${fmt(b.current_power_kw)} kW</span>
            </div>
            <div class="metric">
              <span class="metric__label">Temp</span>
              <span class="metric__value" style="color:${b.temperature_c >= 45 ? 'var(--color-danger)' : 'inherit'}">${fmt(b.temperature_c)} °C</span>
            </div>
            <div class="metric">
              <span class="metric__label">Health</span>
              <span class="metric__value">${fmt(b.health_pct)} %</span>
            </div>
            <div class="metric">
              <span class="metric__label">Cycles</span>
              <span class="metric__value">${b.cycle_count}</span>
            </div>
          </div>
          ${progressBar(b.state_of_charge_pct, "bess")}
          <div style="font-size:.72rem;color:var(--color-text-muted)">${fmt(b.state_of_charge_pct)} % charged · ${fmt(b.capacity_kwh, 0)} kWh total</div>
          ${pill(b.status, b.status)}
        </div>
      `).join("");
    } catch (e) {
      showToast("Failed to load BESS units: " + e.message, "error");
    }
  }

  // ── Mining Rigs ──────────────────────────────────────────────────────────

  async function loadRigs() {
    try {
      const rigs = await apiFetch("/api/mining/rigs");
      if (rigs.length === 0) {
        rigList.innerHTML = "<p class='empty-state'>No mining rigs configured.</p>";
        return;
      }
      rigList.innerHTML = rigs.map((r) => {
        const tempColor = r.chip_temp_c >= 90
          ? "var(--color-crit)"
          : r.chip_temp_c >= 75
            ? "var(--color-warn)"
            : "inherit";
        return `
          <div class="device-card ${r.is_active ? "" : "device-card--inactive"}">
            <div class="device-card__header">
              <span class="device-card__name">⛏ ${esc(r.name)}</span>
              <div class="device-card__actions">
                <button class="btn btn--sm btn--icon" onclick="editRig(${r.id})" title="Edit">✏️</button>
                <button class="btn btn--sm btn--danger" onclick="deleteRig(${r.id},'${esc(r.name)}')" title="Delete">🗑</button>
              </div>
            </div>
            ${r.model ? `<div style="font-size:.75rem;color:var(--color-text-muted)">${esc(r.model)}</div>` : ""}
            <div class="device-card__metrics">
              <div class="metric">
                <span class="metric__label">Hash Rate</span>
                <span class="metric__value" style="color:var(--color-mining)">${fmt(r.current_hash_rate_ths, 2)} TH/s</span>
              </div>
              <div class="metric">
                <span class="metric__label">Power</span>
                <span class="metric__value">${fmt(r.current_power_w, 0)} W</span>
              </div>
              <div class="metric">
                <span class="metric__label">Chip Temp</span>
                <span class="metric__value" style="color:${tempColor}">${fmt(r.chip_temp_c)} °C</span>
              </div>
              <div class="metric">
                <span class="metric__label">Throttle</span>
                <span class="metric__value">${fmt(r.throttle_pct)} %</span>
              </div>
              <div class="metric">
                <span class="metric__label">Efficiency</span>
                <span class="metric__value">${fmt(r.efficiency_ths_per_kw, 3)} TH/kW</span>
              </div>
              <div class="metric">
                <span class="metric__label">Uptime</span>
                <span class="metric__value">${fmt(r.uptime_hours, 0)} h</span>
              </div>
            </div>
            ${progressBar(r.throttle_pct, "mining")}
            <div style="font-size:.72rem;color:var(--color-text-muted)">Throttle ${fmt(r.throttle_pct)} %</div>
            ${pill(r.is_active ? "Active" : "Offline", r.is_active ? "active" : "inactive")}
          </div>`;
      }).join("");
    } catch (e) {
      showToast("Failed to load mining rigs: " + e.message, "error");
    }
  }

  // ── Cooling Zones ─────────────────────────────────────────────────────────

  async function loadZones() {
    try {
      const zones = await apiFetch("/api/cooling/zones");
      if (zones.length === 0) {
        zoneList.innerHTML = "<p class='empty-state'>No cooling zones configured.</p>";
        return;
      }
      zoneList.innerHTML = zones.map((z) => {
        const tempColor = z.temp_status === "critical"
          ? "var(--color-crit)"
          : z.temp_status === "warning"
            ? "var(--color-warn)"
            : "var(--color-cooling)";
        return `
          <div class="device-card ${z.is_active ? "" : "device-card--inactive"}">
            <div class="device-card__header">
              <span class="device-card__name">❄ ${esc(z.name)}</span>
              <div class="device-card__actions">
                <button class="btn btn--sm btn--icon" onclick="editZone(${z.id})" title="Edit">✏️</button>
                <button class="btn btn--sm btn--danger" onclick="deleteZone(${z.id},'${esc(z.name)}')" title="Delete">🗑</button>
              </div>
            </div>
            <div style="font-size:.75rem;color:var(--color-text-muted)">${esc(z.zone_type)}</div>
            <div class="device-card__metrics">
              <div class="metric">
                <span class="metric__label">Temp</span>
                <span class="metric__value" style="color:${tempColor}">${fmt(z.current_temp_c)} °C</span>
              </div>
              <div class="metric">
                <span class="metric__label">Setpoint</span>
                <span class="metric__value">${fmt(z.setpoint_temp_c)} °C</span>
              </div>
              <div class="metric">
                <span class="metric__label">Fan Speed</span>
                <span class="metric__value">${fmt(z.fan_speed_pct)} %</span>
              </div>
              <div class="metric">
                <span class="metric__label">Power</span>
                <span class="metric__value">${fmt(z.current_power_kw)} kW</span>
              </div>
              ${z.coolant_flow_lpm > 0 ? `
              <div class="metric">
                <span class="metric__label">Flow</span>
                <span class="metric__value">${fmt(z.coolant_flow_lpm)} L/min</span>
              </div>` : ""}
            </div>
            ${progressBar(z.fan_speed_pct, "cooling")}
            <div style="font-size:.72rem;color:var(--color-text-muted)">Fan ${fmt(z.fan_speed_pct)} %</div>
            ${pill(z.temp_status, z.temp_status)}
          </div>`;
      }).join("");
    } catch (e) {
      showToast("Failed to load cooling zones: " + e.message, "error");
    }
  }

  // ── AI Recommendations ────────────────────────────────────────────────────

  async function runAIAnalysis() {
    btnAnalyze.disabled = true;
    btnAnalyze.textContent = "⏳ Analysing…";
    try {
      const { summary, recommendations } = await apiFetch("/api/ai/analyze", { method: "POST" });
      pendingRecs = recommendations;
      renderRecommendations(summary, recommendations);
      await loadActionLog();
      await refreshAll();
      showToast(`AI analysis complete – ${recommendations.length} recommendation(s) generated.`);
    } catch (e) {
      showToast("AI analysis failed: " + e.message, "error");
    } finally {
      btnAnalyze.disabled = false;
      btnAnalyze.textContent = "🤖 Run AI Analysis";
    }
  }

  function renderRecommendations(summary, recs) {
    if (recs.length === 0) {
      recommendationsPanel.innerHTML =
        `<p class='empty-state'>✅ All systems nominal – no actions required.</p>`;
      btnExecute.disabled = true;
      return;
    }

    const summaryHtml = `
      <div class="device-card__metrics" style="margin-bottom:.75rem;background:var(--color-surface-2);padding:.65rem 1rem;border-radius:var(--radius-sm);font-size:.85rem;display:grid;grid-template-columns:repeat(5,1fr);gap:.4rem 1rem">
        <div class="metric"><span class="metric__label">Solar</span><span class="metric__value" style="color:var(--color-solar)">${fmt(summary.total_solar_kw)} kW</span></div>
        <div class="metric"><span class="metric__label">BESS SOC</span><span class="metric__value" style="color:var(--color-bess)">${fmt(summary.avg_bess_soc)} %</span></div>
        <div class="metric"><span class="metric__label">Mining</span><span class="metric__value" style="color:var(--color-mining)">${fmt(summary.total_mining_kw)} kW</span></div>
        <div class="metric"><span class="metric__label">Cooling</span><span class="metric__value" style="color:var(--color-cooling)">${fmt(summary.total_cooling_kw)} kW</span></div>
        <div class="metric"><span class="metric__label">Net</span><span class="metric__value" style="color:${summary.net_power_kw >= 0 ? 'var(--color-accent)' : 'var(--color-danger)'}">${summary.net_power_kw >= 0 ? "+" : ""}${fmt(summary.net_power_kw)} kW</span></div>
      </div>`;

    const rows = recs.map((r) => `
      <tr>
        <td><input type="checkbox" class="rec-check" data-id="${r.id}" checked /></td>
        <td>${pill(r.action_type.replace(/_/g, " "), actionPillClass(r.action_type))}</td>
        <td>${esc(r.target_system)}</td>
        <td>${esc(r.target_name || "–")}</td>
        <td>${esc(r.parameter || "–")}</td>
        <td>${r.old_value != null ? fmt(r.old_value, 2) : "–"} → ${r.new_value != null ? fmt(r.new_value, 2) : "–"}</td>
        <td style="max-width:280px;font-size:.8rem">${esc(r.reason)}</td>
        <td>
          ${fmt(r.confidence_score * 100, 0)} %
          <span class="confidence-bar-wrap">
            <span class="confidence-bar" style="width:${fmt(r.confidence_score * 100, 0)}%"></span>
          </span>
        </td>
      </tr>`).join("");

    recommendationsPanel.innerHTML = summaryHtml + `
      <div style="overflow-x:auto">
        <table class="rec-table">
          <thead>
            <tr>
              <th></th><th>Action</th><th>System</th><th>Target</th>
              <th>Parameter</th><th>Change</th><th>Reason</th><th>Confidence</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;

    btnExecute.disabled = false;

    // Sync execute button state with checkboxes
    recommendationsPanel.querySelectorAll(".rec-check").forEach((cb) => {
      cb.addEventListener("change", updateExecuteBtn);
    });
  }

  function actionPillClass(type) {
    if (type.includes("EMERGENCY") || type.includes("SHUTDOWN")) return "critical";
    if (type.includes("REDUCE") || type.includes("STOP"))        return "warning";
    if (type.includes("INCREASE") || type.includes("CHARGE"))    return "active";
    return "ok";
  }

  function updateExecuteBtn() {
    const checked = recommendationsPanel.querySelectorAll(".rec-check:checked").length;
    btnExecute.disabled = checked === 0;
    btnExecute.textContent = `▶ Execute Selected (${checked})`;
  }

  btnSelectAll.addEventListener("click", () => {
    recommendationsPanel.querySelectorAll(".rec-check").forEach((cb) => { cb.checked = true; });
    updateExecuteBtn();
  });

  btnExecute.addEventListener("click", async () => {
    const ids = Array.from(
      recommendationsPanel.querySelectorAll(".rec-check:checked")
    ).map((cb) => parseInt(cb.dataset.id, 10));

    if (ids.length === 0) return;

    btnExecute.disabled = true;
    btnExecute.textContent = "⏳ Executing…";
    try {
      const { count } = await apiFetch("/api/ai/execute", {
        method: "POST",
        body: JSON.stringify({ action_ids: ids }),
      });
      showToast(`${count} action(s) executed successfully.`);
      await refreshAll();
      await loadActionLog();
      // Clear recommendations panel after execution
      recommendationsPanel.innerHTML =
        "<p class='empty-state'>Actions executed – click \"Run AI Analysis\" for next cycle.</p>";
      btnExecute.disabled = true;
      btnExecute.textContent = "▶ Execute Selected";
    } catch (e) {
      showToast("Execution failed: " + e.message, "error");
      btnExecute.disabled = false;
      btnExecute.textContent = `▶ Execute Selected (${ids.length})`;
    }
  });

  // ── Action Log ───────────────────────────────────────────────────────────

  async function loadActionLog() {
    try {
      const actions = await apiFetch("/api/ai/actions");
      actionLogCount.textContent = `${actions.length} record(s)`;

      if (actions.length === 0) {
        actionLog.innerHTML = "<p class='empty-state'>No actions logged yet.</p>";
        return;
      }

      const rows = actions.map((a) => `
        <tr>
          <td style="white-space:nowrap;font-size:.78rem">${fmtDate(a.timestamp)}</td>
          <td>${pill(a.action_type.replace(/_/g, " "), actionPillClass(a.action_type))}</td>
          <td>${esc(a.target_system)}</td>
          <td>${esc(a.target_name || "–")}</td>
          <td>${esc(a.parameter || "–")}</td>
          <td>${a.old_value != null ? fmt(a.old_value, 2) : "–"} → ${a.new_value != null ? fmt(a.new_value, 2) : "–"}</td>
          <td style="max-width:220px;font-size:.78rem">${esc(a.reason)}</td>
          <td class="${a.was_executed ? "log-executed" : "log-unexecuted"}">${a.was_executed ? "✔ Done" : "Pending"}</td>
        </tr>`).join("");

      actionLog.innerHTML = `
        <div style="overflow-x:auto">
          <table class="log-table">
            <thead>
              <tr>
                <th>Time</th><th>Action</th><th>System</th><th>Target</th>
                <th>Parameter</th><th>Change</th><th>Reason</th><th>Status</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`;
    } catch (e) {
      console.error("Failed to load action log:", e);
    }
  }

  // ── Refresh all ──────────────────────────────────────────────────────────

  async function refreshAll() {
    await Promise.all([loadStatus(), loadSolar(), loadBess(), loadRigs(), loadZones()]);
  }

  // ── Solar form ───────────────────────────────────────────────────────────

  const solarModal = document.getElementById("solarModal");
  const solarForm  = document.getElementById("solarForm");

  document.getElementById("btnAddSolar").addEventListener("click", () => {
    document.getElementById("solarModalTitle").textContent = "Add Solar Farm";
    solarForm.reset();
    document.getElementById("solarId").value = "";
    document.getElementById("solarActive").checked = true;
    openModal("solarModal");
  });

  solarForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = document.getElementById("solarId").value;
    const payload = {
      name:               document.getElementById("solarName").value.trim(),
      capacity_kw:        parseFloat(document.getElementById("solarCapacity").value) || 0,
      panel_count:        parseInt(document.getElementById("solarPanels").value) || 0,
      location:           document.getElementById("solarLocation").value.trim() || null,
      current_output_kw:  parseFloat(document.getElementById("solarOutput").value) || 0,
      irradiance_wm2:     parseFloat(document.getElementById("solarIrradiance").value) || 0,
      efficiency_pct:     parseFloat(document.getElementById("solarEfficiency").value) || 0,
      is_active:          document.getElementById("solarActive").checked,
    };
    if (!payload.name) { showToast("Name is required.", "error"); return; }
    try {
      if (id) {
        await apiFetch(`/api/solar/${id}`, { method: "PUT", body: JSON.stringify(payload) });
        showToast("Solar farm updated.");
      } else {
        await apiFetch("/api/solar", { method: "POST", body: JSON.stringify(payload) });
        showToast("Solar farm added.");
      }
      closeModal("solarModal");
      await refreshAll();
    } catch (err) { showToast(err.message, "error"); }
  });

  window.editSolar = async (id) => {
    try {
      const f = await apiFetch(`/api/solar/${id}`);
      document.getElementById("solarModalTitle").textContent = "Edit Solar Farm";
      document.getElementById("solarId").value            = f.id;
      document.getElementById("solarName").value          = f.name;
      document.getElementById("solarCapacity").value      = f.capacity_kw;
      document.getElementById("solarPanels").value        = f.panel_count;
      document.getElementById("solarLocation").value      = f.location || "";
      document.getElementById("solarOutput").value        = f.current_output_kw;
      document.getElementById("solarIrradiance").value    = f.irradiance_wm2;
      document.getElementById("solarEfficiency").value    = f.efficiency_pct;
      document.getElementById("solarActive").checked      = f.is_active;
      openModal("solarModal");
    } catch (err) { showToast(err.message, "error"); }
  };

  window.deleteSolar = async (id, name) => {
    if (!confirm(`Delete solar farm "${name}"?`)) return;
    try {
      await apiFetch(`/api/solar/${id}`, { method: "DELETE" });
      showToast("Solar farm deleted.");
      await refreshAll();
    } catch (err) { showToast(err.message, "error"); }
  };

  // ── BESS form ─────────────────────────────────────────────────────────────

  const bessForm = document.getElementById("bessForm");

  document.getElementById("btnAddBess").addEventListener("click", () => {
    document.getElementById("bessModalTitle").textContent = "Add BESS Unit";
    bessForm.reset();
    document.getElementById("bessId").value = "";
    document.getElementById("bessActive").checked = true;
    document.getElementById("bessHealth").value = 100;
    document.getElementById("bessTemp").value = 25;
    openModal("bessModal");
  });

  bessForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = document.getElementById("bessId").value;
    const payload = {
      name:                  document.getElementById("bessName").value.trim(),
      capacity_kwh:          parseFloat(document.getElementById("bessCapacity").value) || 0,
      state_of_charge_pct:   parseFloat(document.getElementById("bessSoc").value) || 0,
      max_charge_rate_kw:    parseFloat(document.getElementById("bessChargeRate").value) || 0,
      max_discharge_rate_kw: parseFloat(document.getElementById("bessDischargeRate").value) || 0,
      temperature_c:         parseFloat(document.getElementById("bessTemp").value) || 25,
      health_pct:            parseFloat(document.getElementById("bessHealth").value) || 100,
      cycle_count:           parseInt(document.getElementById("bessCycles").value) || 0,
      is_active:             document.getElementById("bessActive").checked,
    };
    if (!payload.name) { showToast("Name is required.", "error"); return; }
    try {
      if (id) {
        await apiFetch(`/api/bess/${id}`, { method: "PUT", body: JSON.stringify(payload) });
        showToast("BESS unit updated.");
      } else {
        await apiFetch("/api/bess", { method: "POST", body: JSON.stringify(payload) });
        showToast("BESS unit added.");
      }
      closeModal("bessModal");
      await refreshAll();
    } catch (err) { showToast(err.message, "error"); }
  });

  window.editBess = async (id) => {
    try {
      const b = await apiFetch(`/api/bess/${id}`);
      document.getElementById("bessModalTitle").textContent    = "Edit BESS Unit";
      document.getElementById("bessId").value                  = b.id;
      document.getElementById("bessName").value                = b.name;
      document.getElementById("bessCapacity").value            = b.capacity_kwh;
      document.getElementById("bessSoc").value                 = b.state_of_charge_pct;
      document.getElementById("bessChargeRate").value          = b.max_charge_rate_kw;
      document.getElementById("bessDischargeRate").value       = b.max_discharge_rate_kw;
      document.getElementById("bessTemp").value                = b.temperature_c;
      document.getElementById("bessHealth").value              = b.health_pct;
      document.getElementById("bessCycles").value              = b.cycle_count;
      document.getElementById("bessActive").checked            = b.is_active;
      openModal("bessModal");
    } catch (err) { showToast(err.message, "error"); }
  };

  window.deleteBess = async (id, name) => {
    if (!confirm(`Delete BESS unit "${name}"?`)) return;
    try {
      await apiFetch(`/api/bess/${id}`, { method: "DELETE" });
      showToast("BESS unit deleted.");
      await refreshAll();
    } catch (err) { showToast(err.message, "error"); }
  };

  // ── Mining Rig form ───────────────────────────────────────────────────────

  const rigForm = document.getElementById("rigForm");

  document.getElementById("btnAddRig").addEventListener("click", () => {
    document.getElementById("rigModalTitle").textContent = "Add Mining Rig";
    rigForm.reset();
    document.getElementById("rigId").value = "";
    document.getElementById("rigThrottle").value = 100;
    document.getElementById("rigAmbientTemp").value = 25;
    openModal("rigModal");
  });

  rigForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = document.getElementById("rigId").value;
    const payload = {
      name:                  document.getElementById("rigName").value.trim(),
      model:                 document.getElementById("rigModel").value.trim() || null,
      max_hash_rate_ths:     parseFloat(document.getElementById("rigMaxHash").value) || 0,
      max_power_w:           parseFloat(document.getElementById("rigMaxPower").value) || 0,
      current_hash_rate_ths: parseFloat(document.getElementById("rigHash").value) || 0,
      current_power_w:       parseFloat(document.getElementById("rigPower").value) || 0,
      chip_temp_c:           parseFloat(document.getElementById("rigChipTemp").value) || 0,
      ambient_temp_c:        parseFloat(document.getElementById("rigAmbientTemp").value) || 25,
      throttle_pct:          parseFloat(document.getElementById("rigThrottle").value) || 100,
      is_active:             document.getElementById("rigActive").checked,
    };
    if (!payload.name) { showToast("Name is required.", "error"); return; }
    try {
      if (id) {
        await apiFetch(`/api/mining/rigs/${id}`, { method: "PUT", body: JSON.stringify(payload) });
        showToast("Mining rig updated.");
      } else {
        await apiFetch("/api/mining/rigs", { method: "POST", body: JSON.stringify(payload) });
        showToast("Mining rig added.");
      }
      closeModal("rigModal");
      await refreshAll();
    } catch (err) { showToast(err.message, "error"); }
  });

  window.editRig = async (id) => {
    try {
      const r = await apiFetch(`/api/mining/rigs/${id}`);
      document.getElementById("rigModalTitle").textContent     = "Edit Mining Rig";
      document.getElementById("rigId").value                   = r.id;
      document.getElementById("rigName").value                 = r.name;
      document.getElementById("rigModel").value                = r.model || "";
      document.getElementById("rigMaxHash").value              = r.max_hash_rate_ths;
      document.getElementById("rigMaxPower").value             = r.max_power_w;
      document.getElementById("rigHash").value                 = r.current_hash_rate_ths;
      document.getElementById("rigPower").value                = r.current_power_w;
      document.getElementById("rigChipTemp").value             = r.chip_temp_c;
      document.getElementById("rigAmbientTemp").value          = r.ambient_temp_c;
      document.getElementById("rigThrottle").value             = r.throttle_pct;
      document.getElementById("rigActive").checked             = r.is_active;
      openModal("rigModal");
    } catch (err) { showToast(err.message, "error"); }
  };

  window.deleteRig = async (id, name) => {
    if (!confirm(`Delete mining rig "${name}"?`)) return;
    try {
      await apiFetch(`/api/mining/rigs/${id}`, { method: "DELETE" });
      showToast("Mining rig deleted.");
      await refreshAll();
    } catch (err) { showToast(err.message, "error"); }
  };

  // ── Cooling Zone form ─────────────────────────────────────────────────────

  const zoneForm = document.getElementById("zoneForm");

  document.getElementById("btnAddZone").addEventListener("click", () => {
    document.getElementById("zoneModalTitle").textContent = "Add Cooling Zone";
    zoneForm.reset();
    document.getElementById("zoneId").value = "";
    document.getElementById("zoneSetpoint").value = 22;
    document.getElementById("zoneMaxTemp").value = 30;
    document.getElementById("zoneMinTemp").value = 18;
    document.getElementById("zoneFanSpeed").value = 50;
    document.getElementById("zoneActive").checked = true;
    openModal("zoneModal");
  });

  zoneForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = document.getElementById("zoneId").value;
    const payload = {
      name:              document.getElementById("zoneName").value.trim(),
      zone_type:         document.getElementById("zoneType").value,
      capacity_kw:       parseFloat(document.getElementById("zoneCapacity").value) || 0,
      setpoint_temp_c:   parseFloat(document.getElementById("zoneSetpoint").value) || 22,
      max_temp_c:        parseFloat(document.getElementById("zoneMaxTemp").value) || 30,
      min_temp_c:        parseFloat(document.getElementById("zoneMinTemp").value) || 18,
      current_temp_c:    parseFloat(document.getElementById("zoneCurrentTemp").value) || 22,
      fan_speed_pct:     parseFloat(document.getElementById("zoneFanSpeed").value) || 50,
      coolant_flow_lpm:  parseFloat(document.getElementById("zoneCoolantFlow").value) || 0,
      is_active:         document.getElementById("zoneActive").checked,
    };
    if (!payload.name) { showToast("Name is required.", "error"); return; }
    try {
      if (id) {
        await apiFetch(`/api/cooling/zones/${id}`, { method: "PUT", body: JSON.stringify(payload) });
        showToast("Cooling zone updated.");
      } else {
        await apiFetch("/api/cooling/zones", { method: "POST", body: JSON.stringify(payload) });
        showToast("Cooling zone added.");
      }
      closeModal("zoneModal");
      await refreshAll();
    } catch (err) { showToast(err.message, "error"); }
  });

  window.editZone = async (id) => {
    try {
      const z = await apiFetch(`/api/cooling/zones/${id}`);
      document.getElementById("zoneModalTitle").textContent    = "Edit Cooling Zone";
      document.getElementById("zoneId").value                  = z.id;
      document.getElementById("zoneName").value                = z.name;
      document.getElementById("zoneType").value                = z.zone_type;
      document.getElementById("zoneCapacity").value            = z.capacity_kw;
      document.getElementById("zoneSetpoint").value            = z.setpoint_temp_c;
      document.getElementById("zoneMaxTemp").value             = z.max_temp_c;
      document.getElementById("zoneMinTemp").value             = z.min_temp_c;
      document.getElementById("zoneCurrentTemp").value         = z.current_temp_c;
      document.getElementById("zoneFanSpeed").value            = z.fan_speed_pct;
      document.getElementById("zoneCoolantFlow").value         = z.coolant_flow_lpm;
      document.getElementById("zoneActive").checked            = z.is_active;
      openModal("zoneModal");
    } catch (err) { showToast(err.message, "error"); }
  };

  window.deleteZone = async (id, name) => {
    if (!confirm(`Delete cooling zone "${name}"?`)) return;
    try {
      await apiFetch(`/api/cooling/zones/${id}`, { method: "DELETE" });
      showToast("Cooling zone deleted.");
      await refreshAll();
    } catch (err) { showToast(err.message, "error"); }
  };

  // ── Event wiring ──────────────────────────────────────────────────────────

  btnRefresh.addEventListener("click", async () => {
    await refreshAll();
    await loadActionLog();
    showToast("Data refreshed.");
  });

  btnAnalyze.addEventListener("click", runAIAnalysis);

  // ── Init ──────────────────────────────────────────────────────────────────

  (async () => {
    await refreshAll();
    await loadActionLog();
  })();

})();
