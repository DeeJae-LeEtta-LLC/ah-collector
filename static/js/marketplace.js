/**
 * AH Collector – Marketplace frontend
 * Manages wallet, world-map regions, trade listings, and auctions.
 */

(() => {
  "use strict";

  // ── Constants ─────────────────────────────────────────────────────────────

  const WALLET_KEY = "ahc_wallet_address";
  const CURRENCIES = ["D33J", "BTC", "ETH"];

  // ── State ─────────────────────────────────────────────────────────────────

  let walletAddress  = localStorage.getItem(WALLET_KEY) || null;
  let allTrades      = [];
  let allRegions     = [];
  let exchangeRates  = {};
  let activeRegionId = null;
  let activeTrade    = null;
  let leafletMap     = null;
  let regionMarkers  = {};

  // ── DOM refs ──────────────────────────────────────────────────────────────

  const toast             = document.getElementById("toast");
  const statOpenTrades    = document.getElementById("statOpenTrades");
  const statAuctions      = document.getElementById("statAuctions");
  const statRegions       = document.getElementById("statRegions");
  const walletStatCard    = document.getElementById("walletStatCard");
  const statWalletAddr    = document.getElementById("statWalletAddr");
  const tradeList         = document.getElementById("tradeList");
  const activeRegionLabel = document.getElementById("activeRegionLabel");

  // ticker
  const tickerD33JBTC = document.getElementById("tickerD33JBTC");
  const tickerD33JETH = document.getElementById("tickerD33JETH");
  const tickerBTCETH  = document.getElementById("tickerBTCETH");

  // wallet modal
  const walletBackdrop    = document.getElementById("walletBackdrop");
  const walletClose       = document.getElementById("walletClose");
  const walletCreateSec   = document.getElementById("walletCreateSection");
  const walletInfoSec     = document.getElementById("walletInfoSection");
  const walletAddress_el  = document.getElementById("walletAddress");
  const balD33J           = document.getElementById("balD33J");
  const balBTC            = document.getElementById("balBTC");
  const balETH            = document.getElementById("balETH");
  const btnNewWallet      = document.getElementById("btnNewWallet");
  const exchangeForm      = document.getElementById("exchangeForm");
  const exchFrom          = document.getElementById("exchFrom");
  const exchTo            = document.getElementById("exchTo");
  const exchAmount        = document.getElementById("exchAmount");
  const exchPreview       = document.getElementById("exchPreview");

  // new listing modal
  const tradeBackdrop     = document.getElementById("tradeBackdrop");
  const tradeClose        = document.getElementById("tradeClose");
  const tradeCancelBtn    = document.getElementById("tradeCancelBtn");
  const tradeForm         = document.getElementById("tradeForm");
  const tradeItemId       = document.getElementById("tradeItemId");
  const tradeSeller       = document.getElementById("tradeSeller");
  const tradePrice        = document.getElementById("tradePrice");
  const tradeCurrency     = document.getElementById("tradeCurrency");
  const tradeRegion       = document.getElementById("tradeRegion");
  const tradeIsAuction    = document.getElementById("tradeIsAuction");
  const auctionHoursRow   = document.getElementById("auctionHoursRow");
  const tradeAuctionHours = document.getElementById("tradeAuctionHours");
  const errorTradeItem    = document.getElementById("errorTradeItem");
  const errorTradeSeller  = document.getElementById("errorTradeSeller");
  const errorTradePrice   = document.getElementById("errorTradePrice");

  // action (buy/bid) modal
  const actionBackdrop    = document.getElementById("actionBackdrop");
  const actionClose       = document.getElementById("actionClose");
  const actionCancelBtn   = document.getElementById("actionCancelBtn");
  const actionModalTitle  = document.getElementById("actionModalTitle");
  const actionBody        = document.getElementById("actionBody");
  const btnBuyNow         = document.getElementById("btnBuyNow");
  const btnPlaceBid       = document.getElementById("btnPlaceBid");

  // nav buttons
  const btnOpenWallet  = document.getElementById("btnOpenWallet");
  const btnCreateTrade = document.getElementById("btnCreateTrade");
  const btnClearRegion = document.getElementById("btnClearRegion");
  const filterCurrency = document.getElementById("filterCurrency");
  const filterType     = document.getElementById("filterType");

  // ── Utility ───────────────────────────────────────────────────────────────

  let toastTimer = null;
  function showToast(msg, type = "success") {
    toast.textContent = msg;
    toast.className = `toast toast--${type}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.add("hidden"), 3500);
  }

  function escHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function shortAddr(addr) {
    if (!addr) return "–";
    return addr.length > 12 ? addr.slice(0, 6) + "…" + addr.slice(-4) : addr;
  }

  function fmtAmount(n, currency) {
    if (n == null) return "–";
    const dec = currency === "D33J" ? 2 : 6;
    return `${parseFloat(n).toFixed(dec)} ${currency}`;
  }

  async function apiFetch(url, opts = {}) {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ description: "Request failed" }));
      throw new Error(err.description || `HTTP ${res.status}`);
    }
    return res.json();
  }

  // ── Exchange rates ────────────────────────────────────────────────────────

  async function loadRates() {
    try {
      exchangeRates = await apiFetch("/api/exchange-rates");
      tickerD33JBTC.textContent = `1 D33J = ${exchangeRates.D33J_BTC} BTC`;
      tickerD33JETH.textContent = `1 D33J = ${exchangeRates.D33J_ETH} ETH`;
      tickerBTCETH.textContent  = `1 BTC = ${exchangeRates.BTC_ETH} ETH`;
    } catch (e) {
      console.error("Failed to load rates:", e);
    }
  }

  // ── Wallet ────────────────────────────────────────────────────────────────

  async function loadWallet() {
    if (!walletAddress) return;
    try {
      const w = await apiFetch(`/api/wallet/${walletAddress}`);
      renderWallet(w);
    } catch {
      // Wallet address stored locally may be stale – clear it
      walletAddress = null;
      localStorage.removeItem(WALLET_KEY);
    }
  }

  function renderWallet(w) {
    walletAddress_el.textContent = w.address;
    balD33J.textContent = w.d33j_balance.toFixed(2);
    balBTC.textContent  = w.btc_balance.toFixed(6);
    balETH.textContent  = w.eth_balance.toFixed(6);
    walletCreateSec.classList.add("hidden");
    walletInfoSec.classList.remove("hidden");

    // Update header stat
    walletStatCard.classList.remove("hidden");
    statWalletAddr.textContent = shortAddr(w.address);

    // Pre-fill seller field in trade modal
    if (tradeSeller) tradeSeller.value = w.address;
  }

  async function createWallet() {
    try {
      const w = await apiFetch("/api/wallet", { method: "POST" });
      walletAddress = w.address;
      localStorage.setItem(WALLET_KEY, walletAddress);
      renderWallet(w);
      showToast("Wallet created!");
    } catch (e) {
      showToast("Failed to create wallet: " + e.message, "error");
    }
  }

  // ── Exchange form ─────────────────────────────────────────────────────────

  function updateExchangePreview() {
    const from   = exchFrom.value;
    const to     = exchTo.value;
    const amount = parseFloat(exchAmount.value);
    if (!from || !to || from === to || isNaN(amount) || amount <= 0) {
      exchPreview.classList.add("hidden");
      return;
    }
    const rate = exchangeRates[`${from}_${to}`];
    if (!rate) { exchPreview.classList.add("hidden"); return; }
    const received = (amount * rate).toFixed(to === "D33J" ? 2 : 6);
    exchPreview.textContent = `≈ ${received} ${to}`;
    exchPreview.classList.remove("hidden");
  }

  [exchFrom, exchTo, exchAmount].forEach(el => el.addEventListener("input", updateExchangePreview));

  exchangeForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!walletAddress) { showToast("Open a wallet first.", "error"); return; }
    const from   = exchFrom.value;
    const to     = exchTo.value;
    const amount = parseFloat(exchAmount.value);
    if (from === to) { showToast("Select two different currencies.", "error"); return; }
    if (isNaN(amount) || amount <= 0) { showToast("Enter a valid amount.", "error"); return; }
    try {
      const result = await apiFetch("/api/exchange", {
        method: "POST",
        body: JSON.stringify({ address: walletAddress, from, to, amount }),
      });
      renderWallet(result.wallet);
      exchAmount.value = "";
      exchPreview.classList.add("hidden");
      showToast(`Exchanged ${amount} ${from} → ${result.received.toFixed(to === "D33J" ? 2 : 8)} ${to}`);
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // ── Regions / Map ─────────────────────────────────────────────────────────

  async function loadRegions() {
    try {
      allRegions = await apiFetch("/api/regions");
      statRegions.textContent = allRegions.length;
      populateRegionSelect();
      if (leafletMap) renderMapMarkers();
    } catch (e) {
      console.error("Failed to load regions:", e);
    }
  }

  function populateRegionSelect() {
    while (tradeRegion.options.length > 1) tradeRegion.remove(1);
    allRegions.forEach(r => {
      const opt = document.createElement("option");
      opt.value = r.id;
      opt.textContent = `${r.name} (tax: ${(r.tax_rate * 100).toFixed(1)}%)`;
      tradeRegion.appendChild(opt);
    });
  }

  function initMap() {
    leafletMap = L.map("worldMap", { zoomControl: true }).setView([20, 0], 2);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a>',
      maxZoom: 6,
    }).addTo(leafletMap);

    renderMapMarkers();
  }

  function renderMapMarkers() {
    // Remove old markers
    Object.values(regionMarkers).forEach(m => leafletMap.removeLayer(m));
    regionMarkers = {};

    allRegions.forEach(r => {
      const isActive = activeRegionId === r.id;
      const marker = L.circleMarker([r.lat, r.lng], {
        radius:      isActive ? 14 : 10,
        fillColor:   isActive ? "#00e5b4" : "#7c5cfc",
        color:       isActive ? "#fff"    : "#9b80fd",
        weight:      2,
        opacity:     1,
        fillOpacity: 0.85,
      }).addTo(leafletMap);

      const popupHtml = `
        <div class="map-popup">
          <strong>${escHtml(r.name)}</strong><br/>
          Tax: ${(r.tax_rate * 100).toFixed(1)}%<br/>
          Open trades: ${r.open_trades ?? "…"}
        </div>`;
      marker.bindPopup(popupHtml);

      marker.on("click", () => {
        activeRegionId = (activeRegionId === r.id) ? null : r.id;
        renderMapMarkers();
        updateRegionLabel();
        loadTrades();
      });

      regionMarkers[r.id] = marker;
    });
  }

  function updateRegionLabel() {
    if (!activeRegionId) {
      activeRegionLabel.classList.add("hidden");
      return;
    }
    const r = allRegions.find(x => x.id === activeRegionId);
    if (r) {
      activeRegionLabel.textContent = `📍 Filtering by: ${r.name}`;
      activeRegionLabel.classList.remove("hidden");
    }
  }

  // ── Trades ────────────────────────────────────────────────────────────────

  async function loadTrades() {
    const params = new URLSearchParams({ status: "open" });
    if (activeRegionId) params.set("region_id", activeRegionId);
    const currency = filterCurrency.value;
    if (currency) params.set("currency", currency);
    const type = filterType.value;
    if (type === "auction") params.set("auction", "true");
    if (type === "direct")  params.set("auction", "false");

    try {
      allTrades = await apiFetch(`/api/trades?${params}`);
    } catch (e) {
      showToast("Failed to load trades: " + e.message, "error");
      allTrades = [];
    }

    const openCount   = allTrades.length;
    const auctionCount = allTrades.filter(t => t.is_auction).length;
    statOpenTrades.textContent = openCount;
    statAuctions.textContent   = auctionCount;

    renderTrades();
  }

  function renderTrades() {
    tradeList.innerHTML = "";
    if (allTrades.length === 0) {
      tradeList.innerHTML = '<p class="empty-state">No listings found.</p>';
      return;
    }
    allTrades.forEach(t => tradeList.appendChild(buildTradeCard(t)));
  }

  function buildTradeCard(t) {
    const card = document.createElement("div");
    card.className = `trade-card${t.is_auction ? " trade-card--auction" : ""}`;

    const endLabel = t.is_auction && t.auction_end
      ? `<span class="trade-end">⏱ Ends ${new Date(t.auction_end).toLocaleString()}</span>`
      : "";
    const topBid = t.top_bid != null
      ? `<div class="trade-top-bid">Top bid: <strong>${fmtAmount(t.top_bid, t.currency)}</strong></div>`
      : "";
    const regionBadge = t.region_name
      ? `<span class="trade-region">📍 ${escHtml(t.region_name)}</span>`
      : "";
    const typeBadge = t.is_auction
      ? `<span class="trade-badge badge--auction">🔨 Auction (${t.bid_count} bids)</span>`
      : `<span class="trade-badge badge--direct">💱 Direct Sale</span>`;

    card.innerHTML = `
      <div class="trade-card__top">
        ${typeBadge}
        ${regionBadge}
      </div>
      <div class="trade-card__name">${escHtml(t.item_name || `Item #${t.item_id}`)}</div>
      <div class="trade-card__price">${fmtAmount(t.price, t.currency)}</div>
      ${topBid}
      ${endLabel}
      <div class="trade-card__seller">Seller: <code>${shortAddr(t.seller_address)}</code></div>
      <div class="trade-card__actions">
        <button class="btn btn--sm btn--primary btn-action">
          ${t.is_auction ? "🔨 Bid" : "🛒 Buy"}
        </button>
      </div>
    `;

    card.querySelector(".btn-action").addEventListener("click", () => openActionModal(t));
    return card;
  }

  // ── Action modal (Buy / Bid) ───────────────────────────────────────────────

  async function openActionModal(trade) {
    activeTrade = trade;
    actionModalTitle.textContent = trade.is_auction ? "🔨 Place a Bid" : "🛒 Buy Now";
    actionBody.innerHTML = '<p class="empty-state">Loading…</p>';
    btnBuyNow.classList.add("hidden");
    btnPlaceBid.classList.add("hidden");
    actionBackdrop.classList.remove("hidden");

    try {
      const data = await apiFetch(`/api/trades/${trade.id}`);
      activeTrade = data;
      renderActionBody(data);
    } catch (err) {
      actionBody.innerHTML = `<p class="empty-state" style="color:var(--color-danger)">${escHtml(err.message)}</p>`;
    }
  }

  function renderActionBody(t) {
    const regionInfo = t.region_name
      ? `<li><strong>Region:</strong> ${escHtml(t.region_name)}</li>`
      : "";

    let taxLine = "";
    if (!t.is_auction) {
      const region = allRegions.find(r => r.id === t.region_id);
      const tax = region ? region.tax_rate : 0;
      const total = t.price * (1 + tax);
      taxLine = `
        <li><strong>Regional Tax:</strong> ${(tax * 100).toFixed(1)}%</li>
        <li><strong>Total Cost:</strong> ${fmtAmount(total, t.currency)}</li>`;
    }

    const bidsHtml = t.bids && t.bids.length > 0
      ? `<table class="history-table" style="margin-top:.5rem">
          <thead><tr><th>#</th><th>Bidder</th><th>Amount</th><th>Placed</th></tr></thead>
          <tbody>
            ${t.bids.map((b, i) => `
              <tr>
                <td>${i + 1}</td>
                <td><code>${shortAddr(b.bidder_address)}</code></td>
                <td>${fmtAmount(b.amount, b.currency)}</td>
                <td>${new Date(b.placed_at).toLocaleString()}</td>
              </tr>`).join("")}
          </tbody>
        </table>`
      : "<p style='color:var(--color-text-muted);font-size:.85rem'>No bids yet.</p>";

    actionBody.innerHTML = `
      <ul class="trade-detail-list">
        <li><strong>Item:</strong> ${escHtml(t.item_name || `#${t.item_id}`)}</li>
        <li><strong>Type:</strong> ${t.is_auction ? "Auction" : "Direct Sale"}</li>
        <li><strong>Starting Price:</strong> ${fmtAmount(t.price, t.currency)}</li>
        ${t.is_auction && t.top_bid != null ? `<li><strong>Top Bid:</strong> ${fmtAmount(t.top_bid, t.currency)}</li>` : ""}
        ${t.is_auction && t.auction_end ? `<li><strong>Ends:</strong> ${new Date(t.auction_end).toLocaleString()}</li>` : ""}
        ${regionInfo}
        ${taxLine}
        <li><strong>Seller:</strong> <code>${shortAddr(t.seller_address)}</code></li>
      </ul>

      ${t.is_auction ? `
        <div class="bid-section">
          <h3 class="bid-title">Bid History</h3>
          ${bidsHtml}
          <div class="form-row" style="margin-top:1rem">
            <label for="bidAmount">Your Bid (${escHtml(t.currency)})</label>
            <input type="number" id="bidAmount" step="any" min="0"
                   placeholder="Min: ${t.top_bid != null ? t.top_bid : t.price}" />
          </div>
          <div class="form-row">
            <label for="bidWallet">Your Wallet Address</label>
            <input type="text" id="bidWallet" value="${escHtml(walletAddress || "")}" maxlength="64" />
          </div>
        </div>` : `
        <div class="form-row" style="margin-top:1rem">
          <label for="buyWallet">Your Wallet Address</label>
          <input type="text" id="buyWallet" value="${escHtml(walletAddress || "")}" maxlength="64" />
        </div>`}
    `;

    if (t.is_auction) {
      btnPlaceBid.classList.remove("hidden");
    } else {
      btnBuyNow.classList.remove("hidden");
    }
  }

  btnPlaceBid.addEventListener("click", async () => {
    if (!activeTrade) return;
    const bidAmountEl = document.getElementById("bidAmount");
    const bidWalletEl = document.getElementById("bidWallet");
    const amount  = parseFloat(bidAmountEl ? bidAmountEl.value : "");
    const bidder  = bidWalletEl ? bidWalletEl.value.trim() : "";

    if (!bidder) { showToast("Enter your wallet address.", "error"); return; }
    if (isNaN(amount) || amount <= 0) { showToast("Enter a valid bid amount.", "error"); return; }

    try {
      await apiFetch(`/api/trades/${activeTrade.id}/bid`, {
        method: "POST",
        body: JSON.stringify({ bidder_address: bidder, amount }),
      });
      showToast("Bid placed successfully!");
      actionBackdrop.classList.add("hidden");
      loadTrades();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  btnBuyNow.addEventListener("click", async () => {
    if (!activeTrade) return;
    const buyWalletEl = document.getElementById("buyWallet");
    const buyer = buyWalletEl ? buyWalletEl.value.trim() : "";
    if (!buyer) { showToast("Enter your wallet address.", "error"); return; }

    try {
      await apiFetch(`/api/trades/${activeTrade.id}/accept`, {
        method: "POST",
        body: JSON.stringify({ buyer_address: buyer }),
      });
      showToast("Trade completed!");
      actionBackdrop.classList.add("hidden");
      loadTrades();
      if (walletAddress) loadWallet();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // ── Items for listing selector ─────────────────────────────────────────────

  async function loadItemsForSelect() {
    try {
      const items = await apiFetch("/api/items");
      while (tradeItemId.options.length > 1) tradeItemId.remove(1);
      items.forEach(it => {
        const opt = document.createElement("option");
        opt.value = it.id;
        opt.textContent = `${it.name}`;
        tradeItemId.appendChild(opt);
      });
    } catch (e) {
      console.error("Failed to load items:", e);
    }
  }

  // ── New Listing Form ──────────────────────────────────────────────────────

  tradeIsAuction.addEventListener("change", () => {
    auctionHoursRow.classList.toggle("hidden", !tradeIsAuction.checked);
  });

  tradeForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorTradeItem.textContent   = "";
    errorTradeSeller.textContent = "";
    errorTradePrice.textContent  = "";

    const itemId   = tradeItemId.value;
    const seller   = tradeSeller.value.trim();
    const price    = parseFloat(tradePrice.value);
    const currency = tradeCurrency.value;
    const regionId = tradeRegion.value || null;
    const isAuction = tradeIsAuction.checked;
    const auctionHours = parseInt(tradeAuctionHours.value, 10) || 24;

    let valid = true;
    if (!itemId)         { errorTradeItem.textContent   = "Select an item.";       valid = false; }
    if (!seller)         { errorTradeSeller.textContent = "Enter wallet address."; valid = false; }
    if (isNaN(price) || price <= 0) { errorTradePrice.textContent = "Enter a valid price."; valid = false; }
    if (!valid) return;

    try {
      await apiFetch("/api/trades", {
        method: "POST",
        body: JSON.stringify({
          item_id:      parseInt(itemId, 10),
          seller_address: seller,
          price,
          currency,
          region_id:    regionId ? parseInt(regionId, 10) : null,
          is_auction:   isAuction,
          auction_hours: auctionHours,
        }),
      });
      showToast("Listing created!");
      tradeBackdrop.classList.add("hidden");
      tradeForm.reset();
      auctionHoursRow.classList.add("hidden");
      loadTrades();
      loadRegions();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // ── Modal wiring ──────────────────────────────────────────────────────────

  function closeAllModals() {
    walletBackdrop.classList.add("hidden");
    tradeBackdrop.classList.add("hidden");
    actionBackdrop.classList.add("hidden");
  }

  btnOpenWallet.addEventListener("click", async () => {
    if (walletAddress) {
      await loadWallet();
    } else {
      walletCreateSec.classList.remove("hidden");
      walletInfoSec.classList.add("hidden");
    }
    walletBackdrop.classList.remove("hidden");
  });

  btnNewWallet.addEventListener("click", createWallet);
  walletClose.addEventListener("click", () => walletBackdrop.classList.add("hidden"));
  walletBackdrop.addEventListener("click", e => { if (e.target === walletBackdrop) walletBackdrop.classList.add("hidden"); });

  btnCreateTrade.addEventListener("click", () => {
    if (walletAddress) tradeSeller.value = walletAddress;
    tradeBackdrop.classList.remove("hidden");
    loadItemsForSelect();
  });
  tradeClose.addEventListener("click", () => tradeBackdrop.classList.add("hidden"));
  tradeCancelBtn.addEventListener("click", () => tradeBackdrop.classList.add("hidden"));
  tradeBackdrop.addEventListener("click", e => { if (e.target === tradeBackdrop) tradeBackdrop.classList.add("hidden"); });

  actionClose.addEventListener("click", () => actionBackdrop.classList.add("hidden"));
  actionCancelBtn.addEventListener("click", () => actionBackdrop.classList.add("hidden"));
  actionBackdrop.addEventListener("click", e => { if (e.target === actionBackdrop) actionBackdrop.classList.add("hidden"); });

  btnClearRegion.addEventListener("click", () => {
    activeRegionId = null;
    renderMapMarkers();
    updateRegionLabel();
    loadTrades();
  });

  filterCurrency.addEventListener("change", loadTrades);
  filterType.addEventListener("change", loadTrades);

  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeAllModals();
  });

  // ── Init ──────────────────────────────────────────────────────────────────

  async function init() {
    await Promise.all([loadRates(), loadRegions()]);
    initMap();
    await loadTrades();
    if (walletAddress) await loadWallet();
  }

  init();
})();
