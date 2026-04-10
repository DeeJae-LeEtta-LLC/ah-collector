/**
 * AH Collector – frontend JavaScript
 * Communicates with the Flask REST API to manage tracked auction-house items.
 */

(() => {
  "use strict";

  // ── State ────────────────────────────────────────────────────────────────

  let allItems = [];
  let currentFilter = { search: "", category: "", watchlisted: false };

  // ── DOM refs ─────────────────────────────────────────────────────────────

  const itemGrid        = document.getElementById("itemGrid");
  const emptyState      = document.getElementById("emptyState");
  const statTotal       = document.getElementById("statTotal");
  const statWatchlisted = document.getElementById("statWatchlisted");
  const statCategories  = document.getElementById("statCategories");
  const statSignups     = document.getElementById("statSignups");
  const filterCategory  = document.getElementById("filterCategory");
  const searchInput     = document.getElementById("searchInput");

  // nav buttons
  const btnShowAll       = document.getElementById("btnShowAll");
  const btnShowWatchlist = document.getElementById("btnShowWatchlist");
  const btnAddItem       = document.getElementById("btnAddItem");

  // item modal
  const modalBackdrop = document.getElementById("modalBackdrop");
  const modalTitle    = document.getElementById("modalTitle");
  const itemForm      = document.getElementById("itemForm");
  const modalClose    = document.getElementById("modalClose");
  const btnCancel     = document.getElementById("btnCancel");
  const btnSubmit     = document.getElementById("btnSubmit");

  const fieldId          = document.getElementById("fieldId");
  const fieldName        = document.getElementById("fieldName");
  const fieldCollection  = document.getElementById("fieldCollection");
  const fieldCategory    = document.getElementById("fieldCategory");
  const fieldPrice       = document.getElementById("fieldPrice");
  const fieldMinPrice    = document.getElementById("fieldMinPrice");
  const fieldMaxPrice    = document.getElementById("fieldMaxPrice");
  const fieldNotes       = document.getElementById("fieldNotes");
  const fieldWatchlisted = document.getElementById("fieldWatchlisted");
  const errorName        = document.getElementById("errorName");
  const errorPrice       = document.getElementById("errorPrice");

  // history modal
  const historyBackdrop = document.getElementById("historyBackdrop");
  const historyTitle    = document.getElementById("historyTitle");
  const historyBody     = document.getElementById("historyBody");
  const historyClose    = document.getElementById("historyClose");

  // toast
  const toast = document.getElementById("toast");

  // ── Toast ────────────────────────────────────────────────────────────────

  let toastTimer = null;

  function showToast(message, type = "success") {
    toast.textContent = message;
    toast.className = `toast toast--${type}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.classList.add("hidden"); }, 3000);
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

  // ── Load data ────────────────────────────────────────────────────────────

  async function loadStats() {
    try {
      const data = await apiFetch("/api/stats");
      statTotal.textContent       = data.total_items;
      statWatchlisted.textContent = data.watchlisted_items;
      statCategories.textContent  = data.categories.length;

      // Populate category filter
      const currentVal = filterCategory.value;
      // Remove existing options except the first ("All categories")
      while (filterCategory.options.length > 1) {
        filterCategory.remove(1);
      }
      data.categories.forEach(({ category }) => {
        const opt = document.createElement("option");
        opt.value = category;
        opt.textContent = category;
        if (category === currentVal) opt.selected = true;
        filterCategory.appendChild(opt);
      });
    } catch (e) {
      console.error("Failed to load stats:", e);
    }

    try {
      const obData = await apiFetch("/api/onboard/stats");
      if (statSignups) statSignups.textContent = obData.total_signups;
    } catch (e) {
      console.error("Failed to load signup stats:", e);
    }
  }

  async function loadItems() {
    const params = new URLSearchParams();
    if (currentFilter.search)    params.set("search",     currentFilter.search);
    if (currentFilter.category)  params.set("category",   currentFilter.category);
    if (currentFilter.watchlisted) params.set("watchlisted", "true");

    try {
      allItems = await apiFetch(`/api/items?${params.toString()}`);
    } catch (e) {
      showToast("Failed to load items: " + e.message, "error");
      allItems = [];
    }
    renderGrid();
  }

  async function refreshAll() {
    await loadStats();
    await loadItems();
  }

  // ── Render ───────────────────────────────────────────────────────────────

  function formatPrice(eth) {
    if (eth == null) return "–";
    return `${parseFloat(eth).toFixed(4)} ETH`;
  }

  function formatDate(iso) {
    if (!iso) return "–";
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric", month: "short", day: "numeric",
    });
  }

  function renderGrid() {
    itemGrid.innerHTML = "";

    if (allItems.length === 0) {
      const p = document.createElement("p");
      p.className = "empty-state";
      p.textContent = currentFilter.watchlisted
        ? "No watchlisted items found."
        : "No items found. Click '+ Add Item' to get started.";
      itemGrid.appendChild(p);
      return;
    }

    allItems.forEach((item) => {
      itemGrid.appendChild(buildCard(item));
    });
  }

  function buildCard(item) {
    const card = document.createElement("div");
    card.className = `item-card${item.is_watchlisted ? " watchlisted" : ""}`;
    card.dataset.id = item.id;

    const priceAlerts = [];
    if (item.min_price != null && item.current_price <= item.min_price) {
      priceAlerts.push(`⬇ Below min ${formatPrice(item.min_price)}`);
    }
    if (item.max_price != null && item.current_price >= item.max_price) {
      priceAlerts.push(`⬆ Above max ${formatPrice(item.max_price)}`);
    }

    card.innerHTML = `
      ${item.is_watchlisted ? '<span class="item-card__badge badge--watchlist">👁 Watching</span>' : ""}
      <div class="item-card__name">${escHtml(item.name)}</div>
      ${item.collection ? `<div class="item-card__collection">📦 ${escHtml(item.collection)}</div>` : ""}
      ${item.category && item.category !== "Uncategorized"
        ? `<span class="item-card__badge badge--category" style="position:static;display:inline-block;margin-top:-.2rem">${escHtml(item.category)}</span>`
        : ""}
      <div>
        <div class="item-card__price">${formatPrice(item.current_price)}</div>
        ${priceAlerts.length
          ? `<div class="item-card__price-sub" style="color:var(--color-warning)">${priceAlerts.join(" · ")}</div>`
          : item.min_price != null || item.max_price != null
            ? `<div class="item-card__price-sub">Range: ${formatPrice(item.min_price)} – ${formatPrice(item.max_price)}</div>`
            : ""}
      </div>
      ${item.notes ? `<div class="item-card__notes">${escHtml(item.notes)}</div>` : ""}
      <div class="item-card__actions">
        <button class="btn btn--sm btn--outline btn-edit" title="Edit">✏️ Edit</button>
        <button class="btn btn--sm btn--icon btn-history" title="Price history">📈</button>
        <button class="btn btn--sm btn--icon btn-watch" title="${item.is_watchlisted ? "Remove from watchlist" : "Add to watchlist"}">
          ${item.is_watchlisted ? "⭐" : "☆"}
        </button>
        <button class="btn btn--sm btn--danger btn-delete" title="Delete">🗑</button>
      </div>
    `;

    card.querySelector(".btn-edit").addEventListener("click", () => openEditModal(item));
    card.querySelector(".btn-history").addEventListener("click", () => openHistory(item));
    card.querySelector(".btn-watch").addEventListener("click", () => toggleWatch(item));
    card.querySelector(".btn-delete").addEventListener("click", () => deleteItem(item));

    return card;
  }

  // ── Modal helpers ────────────────────────────────────────────────────────

  function openAddModal() {
    modalTitle.textContent   = "Add Item";
    btnSubmit.textContent    = "Add Item";
    fieldId.value            = "";
    fieldName.value          = "";
    fieldCollection.value    = "";
    fieldCategory.value      = "";
    fieldPrice.value         = "";
    fieldMinPrice.value      = "";
    fieldMaxPrice.value      = "";
    fieldNotes.value         = "";
    fieldWatchlisted.checked = false;
    clearErrors();
    modalBackdrop.classList.remove("hidden");
    fieldName.focus();
  }

  function openEditModal(item) {
    modalTitle.textContent   = "Edit Item";
    btnSubmit.textContent    = "Save Changes";
    fieldId.value            = item.id;
    fieldName.value          = item.name;
    fieldCollection.value    = item.collection || "";
    fieldCategory.value      = item.category === "Uncategorized" ? "" : item.category;
    fieldPrice.value         = item.current_price;
    fieldMinPrice.value      = item.min_price != null ? item.min_price : "";
    fieldMaxPrice.value      = item.max_price != null ? item.max_price : "";
    fieldNotes.value         = item.notes || "";
    fieldWatchlisted.checked = item.is_watchlisted;
    clearErrors();
    modalBackdrop.classList.remove("hidden");
    fieldName.focus();
  }

  function closeModal() {
    modalBackdrop.classList.add("hidden");
  }

  function clearErrors() {
    errorName.textContent  = "";
    errorPrice.textContent = "";
  }

  // ── Form submit ──────────────────────────────────────────────────────────

  itemForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearErrors();

    const name  = fieldName.value.trim();
    const price = fieldPrice.value.trim();
    let valid   = true;

    if (!name) {
      errorName.textContent = "Name is required.";
      valid = false;
    }
    if (price === "" || isNaN(Number(price)) || Number(price) < 0) {
      errorPrice.textContent = "A valid price (≥ 0) is required.";
      valid = false;
    }
    if (!valid) return;

    const payload = {
      name,
      collection:    fieldCollection.value.trim() || null,
      category:      fieldCategory.value.trim() || "Uncategorized",
      current_price: parseFloat(price),
      min_price:     fieldMinPrice.value !== "" ? parseFloat(fieldMinPrice.value) : null,
      max_price:     fieldMaxPrice.value !== "" ? parseFloat(fieldMaxPrice.value) : null,
      notes:         fieldNotes.value.trim() || null,
      is_watchlisted: fieldWatchlisted.checked,
    };

    const id = fieldId.value;
    try {
      if (id) {
        await apiFetch(`/api/items/${id}`, { method: "PUT", body: JSON.stringify(payload) });
        showToast("Item updated.");
      } else {
        await apiFetch("/api/items", { method: "POST", body: JSON.stringify(payload) });
        showToast("Item added.");
      }
      closeModal();
      refreshAll();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // ── Delete ───────────────────────────────────────────────────────────────

  async function deleteItem(item) {
    if (!confirm(`Delete "${item.name}"?`)) return;
    try {
      await apiFetch(`/api/items/${item.id}`, { method: "DELETE" });
      showToast("Item deleted.");
      refreshAll();
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  // ── Watchlist toggle ──────────────────────────────────────────────────────

  async function toggleWatch(item) {
    try {
      const data = await apiFetch(`/api/items/${item.id}/watchlist`, { method: "POST" });
      showToast(data.is_watchlisted ? "Added to watchlist." : "Removed from watchlist.");
      refreshAll();
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  // ── Price history ─────────────────────────────────────────────────────────

  async function openHistory(item) {
    historyTitle.textContent = `Price History – ${item.name}`;
    historyBody.innerHTML    = "<p class='empty-state'>Loading…</p>";
    historyBackdrop.classList.remove("hidden");

    try {
      const data = await apiFetch(`/api/items/${item.id}`);
      const history = data.price_history || [];

      if (history.length === 0) {
        historyBody.innerHTML = "<p class='empty-state'>No price history recorded yet.</p>";
        return;
      }

      const table = document.createElement("table");
      table.className = "history-table";
      table.innerHTML = `
        <thead>
          <tr>
            <th>#</th>
            <th>Price (ETH)</th>
            <th>Recorded At</th>
          </tr>
        </thead>
        <tbody>
          ${history.map((h, i) => `
            <tr>
              <td>${i + 1}</td>
              <td>${parseFloat(h.price).toFixed(4)}</td>
              <td>${new Date(h.recorded_at).toLocaleString()}</td>
            </tr>
          `).join("")}
        </tbody>
      `;
      historyBody.innerHTML = "";
      historyBody.appendChild(table);
    } catch (err) {
      historyBody.innerHTML = `<p class='empty-state' style='color:var(--color-danger)'>Failed to load history: ${escHtml(err.message)}</p>`;
    }
  }

  // ── Filters / search ──────────────────────────────────────────────────────

  let searchTimer = null;

  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      currentFilter.search = searchInput.value.trim();
      loadItems();
    }, 300);
  });

  filterCategory.addEventListener("change", () => {
    currentFilter.category = filterCategory.value;
    loadItems();
  });

  btnShowAll.addEventListener("click", () => {
    currentFilter.watchlisted = false;
    btnShowAll.classList.add("active");
    btnShowWatchlist.classList.remove("active");
    loadItems();
  });

  btnShowWatchlist.addEventListener("click", () => {
    currentFilter.watchlisted = true;
    btnShowWatchlist.classList.add("active");
    btnShowAll.classList.remove("active");
    loadItems();
  });

  // ── Event wiring ─────────────────────────────────────────────────────────

  btnAddItem.addEventListener("click", openAddModal);
  modalClose.addEventListener("click", closeModal);
  btnCancel.addEventListener("click", closeModal);
  historyClose.addEventListener("click", () => historyBackdrop.classList.add("hidden"));

  // Close modal on backdrop click
  modalBackdrop.addEventListener("click", (e) => {
    if (e.target === modalBackdrop) closeModal();
  });
  historyBackdrop.addEventListener("click", (e) => {
    if (e.target === historyBackdrop) historyBackdrop.classList.add("hidden");
  });

  // Keyboard: Escape closes modals
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeModal();
      historyBackdrop.classList.add("hidden");
    }
  });

  // ── Utility ──────────────────────────────────────────────────────────────

  function escHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ── Init ─────────────────────────────────────────────────────────────────

  btnShowAll.classList.add("active");
  refreshAll();
})();
