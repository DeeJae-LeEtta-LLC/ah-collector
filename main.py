"""
AH Collector - Auction House Collector Application
Flask backend providing REST API and serving the frontend.
Includes marketplace with D33J/BTC/ETH support, world-map regions,
auction bidding, and a multi-currency wallet system.
"""

import os
import secrets
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc, func

app = Flask(__name__)

# Database configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///" + os.path.join(basedir, "ah_collector.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ──────────────────────────────────────────────────────────────────────────────
# Error handlers
# ──────────────────────────────────────────────────────────────────────────────

@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(405)
def handle_http_error(e):
    """Return all HTTP errors as JSON."""
    return jsonify({"description": e.description}), e.code


# ──────────────────────────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────────────────────────

class Item(db.Model):
    """Represents an auction house item being tracked."""

    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False, default="Uncategorized")
    current_price = db.Column(db.Float, nullable=False, default=0.0)
    min_price = db.Column(db.Float, nullable=True)
    max_price = db.Column(db.Float, nullable=True)
    collection = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_watchlisted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    price_history = db.relationship(
        "PriceHistory", backref="item", lazy=True, cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "current_price": self.current_price,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "collection": self.collection,
            "notes": self.notes,
            "is_watchlisted": self.is_watchlisted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PriceHistory(db.Model):
    """Records price changes for tracked items."""

    __tablename__ = "price_history"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    price = db.Column(db.Float, nullable=False)
    recorded_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self):
        return {
            "id": self.id,
            "item_id": self.item_id,
            "price": self.price,
            "recorded_at": (
                self.recorded_at.isoformat() if self.recorded_at else None
            ),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Marketplace Models
# ──────────────────────────────────────────────────────────────────────────────

class Wallet(db.Model):
    """Multi-currency wallet (D33J / BTC / ETH) for a player."""

    __tablename__ = "wallets"

    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(64), unique=True, nullable=False)
    d33j_balance = db.Column(db.Float, nullable=False, default=1000.0)
    btc_balance  = db.Column(db.Float, nullable=False, default=0.01)
    eth_balance  = db.Column(db.Float, nullable=False, default=0.5)
    created_at   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "address":      self.address,
            "d33j_balance": self.d33j_balance,
            "btc_balance":  self.btc_balance,
            "eth_balance":  self.eth_balance,
            "created_at":   self.created_at.isoformat() if self.created_at else None,
        }


class MapRegion(db.Model):
    """A named trading region shown on the world map."""

    __tablename__ = "map_regions"

    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(100), nullable=False)
    tax_rate = db.Column(db.Float, nullable=False, default=0.02)   # e.g. 0.02 = 2 %
    lat      = db.Column(db.Float, nullable=False)
    lng      = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return {
            "id":       self.id,
            "name":     self.name,
            "tax_rate": self.tax_rate,
            "lat":      self.lat,
            "lng":      self.lng,
        }


class Trade(db.Model):
    """A marketplace listing (direct sale or auction)."""

    __tablename__ = "trades"

    id               = db.Column(db.Integer, primary_key=True)
    item_id          = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    seller_address   = db.Column(db.String(64), nullable=False)
    buyer_address    = db.Column(db.String(64), nullable=True)
    price            = db.Column(db.Float, nullable=False)
    currency         = db.Column(db.String(10), nullable=False, default="ETH")  # D33J | BTC | ETH
    region_id        = db.Column(db.Integer, db.ForeignKey("map_regions.id"), nullable=True)
    status           = db.Column(db.String(20), nullable=False, default="open")  # open | completed | cancelled
    is_auction       = db.Column(db.Boolean, default=False)
    auction_end      = db.Column(db.DateTime, nullable=True)
    created_at       = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at       = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    item   = db.relationship("Item",      backref="trades",  lazy=True)
    region = db.relationship("MapRegion", backref="trades",  lazy=True)
    bids   = db.relationship("Bid",       backref="trade",   lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id":             self.id,
            "item_id":        self.item_id,
            "item_name":      self.item.name if self.item else None,
            "seller_address": self.seller_address,
            "buyer_address":  self.buyer_address,
            "price":          self.price,
            "currency":       self.currency,
            "region_id":      self.region_id,
            "region_name":    self.region.name if self.region else None,
            "status":         self.status,
            "is_auction":     self.is_auction,
            "auction_end":    self.auction_end.isoformat() if self.auction_end else None,
            "created_at":     self.created_at.isoformat() if self.created_at else None,
            "updated_at":     self.updated_at.isoformat() if self.updated_at else None,
            "bid_count":      len(self.bids),
            "top_bid":        max((b.amount for b in self.bids), default=None),
        }


class Bid(db.Model):
    """A bid placed on an auction-type Trade."""

    __tablename__ = "bids"

    id              = db.Column(db.Integer, primary_key=True)
    trade_id        = db.Column(db.Integer, db.ForeignKey("trades.id"), nullable=False)
    bidder_address  = db.Column(db.String(64), nullable=False)
    amount          = db.Column(db.Float, nullable=False)
    currency        = db.Column(db.String(10), nullable=False, default="ETH")
    placed_at       = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id":             self.id,
            "trade_id":       self.trade_id,
            "bidder_address": self.bidder_address,
            "amount":         self.amount,
            "currency":       self.currency,
            "placed_at":      self.placed_at.isoformat() if self.placed_at else None,
        }


# ──────────────────────────────────────────────────────────────────────────────
# In-memory exchange rates  (D33J is the game-native coin)
# 1 D33J expressed in BTC / ETH; 1 BTC expressed in ETH
# ──────────────────────────────────────────────────────────────────────────────

EXCHANGE_RATES = {
    "D33J_BTC": 0.000001,   # 1 D33J = 0.000001 BTC
    "D33J_ETH": 0.00001,    # 1 D33J = 0.00001  ETH
    "BTC_ETH":  15.0,       # 1 BTC  = 15 ETH   (demo value)
    "BTC_D33J": 1_000_000,  # inverse
    "ETH_D33J": 100_000,    # inverse
    "ETH_BTC":  0.0667,     # inverse
}

VALID_CURRENCIES = {"D33J", "BTC", "ETH"}

# ──────────────────────────────────────────────────────────────────────────────
# Seed data helpers
# ──────────────────────────────────────────────────────────────────────────────

_MAP_REGION_SEEDS = [
    {"name": "Northern Kingdoms",  "tax_rate": 0.01, "lat": 60.0,  "lng":  10.0},
    {"name": "Desert Expanse",     "tax_rate": 0.03, "lat": 20.0,  "lng":  30.0},
    {"name": "Eastern Dominion",   "tax_rate": 0.02, "lat": 35.0,  "lng": 100.0},
    {"name": "Western Reaches",    "tax_rate": 0.015,"lat": 40.0,  "lng": -80.0},
    {"name": "Southern Isles",     "tax_rate": 0.025,"lat":-20.0,  "lng":  50.0},
    {"name": "Frozen Tundra",      "tax_rate": 0.005,"lat": 70.0,  "lng": -30.0},
    {"name": "Ancient Heartlands", "tax_rate": 0.02, "lat": 48.0,  "lng":  15.0},
]


def _seed_regions():
    """Insert default map regions if the table is empty."""
    if MapRegion.query.count() == 0:
        for r in _MAP_REGION_SEEDS:
            db.session.add(MapRegion(**r))
        db.session.commit()


# ──────────────────────────────────────────────────────────────────────────────
# Frontend routes
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main dashboard."""
    return render_template("index.html")


@app.route("/marketplace")
def marketplace():
    """Serve the marketplace world-map page."""
    return render_template("marketplace.html")


# ──────────────────────────────────────────────────────────────────────────────
# API routes
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/items", methods=["GET"])
def get_items():
    """Return all tracked items, with optional search/filter."""
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    watchlisted = request.args.get("watchlisted", "").strip().lower()

    query = Item.query

    if search:
        query = query.filter(
            Item.name.ilike(f"%{search}%") | Item.collection.ilike(f"%{search}%")
        )
    if category:
        query = query.filter(Item.category.ilike(f"%{category}%"))
    if watchlisted == "true":
        query = query.filter(Item.is_watchlisted.is_(True))

    items = query.order_by(desc(Item.updated_at)).all()
    return jsonify([item.to_dict() for item in items])


@app.route("/api/items/<int:item_id>", methods=["GET"])
def get_item(item_id):
    """Return a single item with its price history."""
    item = db.get_or_404(Item, item_id)
    data = item.to_dict()
    data["price_history"] = [
        ph.to_dict()
        for ph in PriceHistory.query.filter_by(item_id=item_id)
        .order_by(PriceHistory.recorded_at)
        .all()
    ]
    return jsonify(data)


@app.route("/api/items", methods=["POST"])
def create_item():
    """Create a new tracked item."""
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")

    name = payload.get("name", "").strip()
    if not name:
        abort(400, description="'name' is required.")

    price = payload.get("current_price", 0.0)
    try:
        price = float(price)
    except (TypeError, ValueError):
        abort(400, description="'current_price' must be a number.")

    item = Item(
        name=name,
        category=payload.get("category", "Uncategorized"),
        current_price=price,
        min_price=payload.get("min_price"),
        max_price=payload.get("max_price"),
        collection=payload.get("collection"),
        notes=payload.get("notes"),
        is_watchlisted=bool(payload.get("is_watchlisted", False)),
    )
    db.session.add(item)
    db.session.flush()  # get item.id before adding price history

    # Record the initial price in history
    ph = PriceHistory(item_id=item.id, price=price)
    db.session.add(ph)
    db.session.commit()

    return jsonify(item.to_dict()), 201


@app.route("/api/items/<int:item_id>", methods=["PUT"])
def update_item(item_id):
    """Update an existing item (and record price change if price differs)."""
    item = db.get_or_404(Item, item_id)
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")

    if "name" in payload:
        name = payload["name"].strip()
        if not name:
            abort(400, description="'name' cannot be empty.")
        item.name = name

    if "category" in payload:
        item.category = payload["category"]
    if "collection" in payload:
        item.collection = payload["collection"]
    if "notes" in payload:
        item.notes = payload["notes"]
    if "is_watchlisted" in payload:
        item.is_watchlisted = bool(payload["is_watchlisted"])
    if "min_price" in payload:
        item.min_price = payload["min_price"]
    if "max_price" in payload:
        item.max_price = payload["max_price"]

    if "current_price" in payload:
        new_price = payload["current_price"]
        try:
            new_price = float(new_price)
        except (TypeError, ValueError):
            abort(400, description="'current_price' must be a number.")

        if new_price != item.current_price:
            ph = PriceHistory(item_id=item.id, price=new_price)
            db.session.add(ph)
            item.current_price = new_price

    item.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(item.to_dict())


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    """Delete a tracked item."""
    item = db.get_or_404(Item, item_id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": f"Item {item_id} deleted."})


@app.route("/api/items/<int:item_id>/watchlist", methods=["POST"])
def toggle_watchlist(item_id):
    """Toggle the watchlist status of an item."""
    item = db.get_or_404(Item, item_id)
    item.is_watchlisted = not item.is_watchlisted
    item.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"is_watchlisted": item.is_watchlisted})


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Return summary statistics for the dashboard."""
    total = Item.query.count()
    watchlisted = Item.query.filter_by(is_watchlisted=True).count()

    # Category breakdown
    categories = (
        db.session.query(Item.category, func.count(Item.id))
        .group_by(Item.category)
        .all()
    )
    category_data = [{"category": c, "count": n} for c, n in categories]

    return jsonify(
        {
            "total_items": total,
            "watchlisted_items": watchlisted,
            "categories": category_data,
        }
    )


# ──────────────────────────────────────────────────────────────────────────────
# Marketplace API – Wallet
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/wallet", methods=["POST"])
def create_wallet():
    """Create a new wallet and return its address and starting balances."""
    from sqlalchemy.exc import IntegrityError
    for _ in range(5):
        address = secrets.token_hex(20)   # 40-char hex string  (160-bit)
        try:
            wallet = Wallet(address=address)
            db.session.add(wallet)
            db.session.commit()
            return jsonify(wallet.to_dict()), 201
        except IntegrityError:
            db.session.rollback()
    abort(500, description="Failed to generate unique wallet address.")


@app.route("/api/wallet/<address>", methods=["GET"])
def get_wallet(address):
    """Return wallet balances for the given address."""
    wallet = Wallet.query.filter_by(address=address).first_or_404()
    return jsonify(wallet.to_dict())


# ──────────────────────────────────────────────────────────────────────────────
# Marketplace API – Exchange rates & currency conversion
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/exchange-rates", methods=["GET"])
def get_exchange_rates():
    """Return current exchange rates between D33J, BTC, and ETH."""
    return jsonify(EXCHANGE_RATES)


@app.route("/api/exchange", methods=["POST"])
def exchange_currency():
    """
    Exchange currencies within a wallet.
    Body: { "address": "...", "from": "D33J", "to": "ETH", "amount": 100.0 }
    """
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")

    address = payload.get("address", "").strip()
    from_currency = payload.get("from", "").upper()
    to_currency   = payload.get("to",   "").upper()
    amount_raw    = payload.get("amount")

    if not address:
        abort(400, description="'address' is required.")
    if from_currency not in VALID_CURRENCIES:
        abort(400, description=f"'from' must be one of {sorted(VALID_CURRENCIES)}.")
    if to_currency not in VALID_CURRENCIES:
        abort(400, description=f"'to' must be one of {sorted(VALID_CURRENCIES)}.")
    if from_currency == to_currency:
        abort(400, description="'from' and 'to' must be different currencies.")

    try:
        amount = float(amount_raw)
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        abort(400, description="'amount' must be a positive number.")

    wallet = Wallet.query.filter_by(address=address).first_or_404()

    # Check source balance
    bal_attr = f"{from_currency.lower()}_balance"
    source_balance = getattr(wallet, bal_attr)
    if source_balance < amount:
        abort(400, description=f"Insufficient {from_currency} balance.")

    rate_key = f"{from_currency}_{to_currency}"
    rate = EXCHANGE_RATES.get(rate_key)
    if rate is None:
        abort(400, description="No exchange rate available for this pair.")

    converted = amount * rate

    # Debit source, credit destination
    setattr(wallet, bal_attr, source_balance - amount)
    to_bal_attr = f"{to_currency.lower()}_balance"
    setattr(wallet, to_bal_attr, getattr(wallet, to_bal_attr) + converted)
    db.session.commit()

    return jsonify({
        "from":       from_currency,
        "to":         to_currency,
        "spent":      amount,
        "received":   converted,
        "rate":       rate,
        "wallet":     wallet.to_dict(),
    })


# ──────────────────────────────────────────────────────────────────────────────
# Marketplace API – Regions
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/regions", methods=["GET"])
def get_regions():
    """Return all map regions with trade counts."""
    regions = MapRegion.query.all()
    result = []
    for r in regions:
        d = r.to_dict()
        d["open_trades"] = Trade.query.filter_by(region_id=r.id, status="open").count()
        result.append(d)
    return jsonify(result)


# ──────────────────────────────────────────────────────────────────────────────
# Marketplace API – Trades
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/trades", methods=["GET"])
def get_trades():
    """List marketplace trades with optional filters."""
    status    = request.args.get("status",    "open")
    currency  = request.args.get("currency",  "").upper()
    region_id = request.args.get("region_id", "")
    is_auction = request.args.get("auction",  "")

    query = Trade.query
    if status:
        query = query.filter(Trade.status == status)
    if currency and currency in VALID_CURRENCIES:
        query = query.filter(Trade.currency == currency)
    if region_id.isdigit():
        query = query.filter(Trade.region_id == int(region_id))
    if is_auction.lower() == "true":
        query = query.filter(Trade.is_auction.is_(True))
    elif is_auction.lower() == "false":
        query = query.filter(Trade.is_auction.is_(False))

    trades = query.order_by(desc(Trade.created_at)).all()
    return jsonify([t.to_dict() for t in trades])


@app.route("/api/trades", methods=["POST"])
def create_trade():
    """Create a new trade listing (direct sale or auction)."""
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")

    item_id = payload.get("item_id")
    if not item_id:
        abort(400, description="'item_id' is required.")
    db.get_or_404(Item, item_id)   # validates item exists

    seller = payload.get("seller_address", "").strip()
    if not seller:
        abort(400, description="'seller_address' is required.")

    # Validate wallet exists
    wallet = Wallet.query.filter_by(address=seller).first()
    if not wallet:
        abort(400, description="Seller wallet not found.")

    currency = payload.get("currency", "ETH").upper()
    if currency not in VALID_CURRENCIES:
        abort(400, description=f"'currency' must be one of {sorted(VALID_CURRENCIES)}.")

    try:
        price = float(payload.get("price", 0))
        if price <= 0:
            raise ValueError
    except (TypeError, ValueError):
        abort(400, description="'price' must be a positive number.")

    is_auction = bool(payload.get("is_auction", False))
    auction_end = None
    if is_auction:
        hours_raw = payload.get("auction_hours", 24)
        try:
            hours = max(1, int(hours_raw))
        except (TypeError, ValueError):
            hours = 24
        from datetime import timedelta
        auction_end = datetime.now(timezone.utc) + timedelta(hours=hours)

    region_id_raw = payload.get("region_id")
    region_id = None
    if region_id_raw is not None:
        try:
            region_id = int(region_id_raw)
            if not db.session.get(MapRegion, region_id):
                region_id = None
        except (TypeError, ValueError):
            region_id = None

    trade = Trade(
        item_id=item_id,
        seller_address=seller,
        price=price,
        currency=currency,
        region_id=region_id,
        is_auction=is_auction,
        auction_end=auction_end,
    )
    db.session.add(trade)
    db.session.commit()
    return jsonify(trade.to_dict()), 201


@app.route("/api/trades/<int:trade_id>", methods=["GET"])
def get_trade(trade_id):
    """Return a single trade with its bids."""
    trade = db.get_or_404(Trade, trade_id)
    data = trade.to_dict()
    data["bids"] = [b.to_dict() for b in
                    Bid.query.filter_by(trade_id=trade_id)
                    .order_by(desc(Bid.amount)).all()]
    return jsonify(data)


@app.route("/api/trades/<int:trade_id>/bid", methods=["POST"])
def place_bid(trade_id):
    """Place a bid on an auction-type trade."""
    trade = db.get_or_404(Trade, trade_id)

    if not trade.is_auction:
        abort(400, description="This trade is not an auction.")
    if trade.status != "open":
        abort(400, description="This auction is no longer open.")
    if trade.auction_end:
        # auction_end may be naive (as stored by SQLite); treat it as UTC
        end_utc = trade.auction_end if trade.auction_end.tzinfo else trade.auction_end.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > end_utc:
            trade.status = "completed"
            db.session.commit()
            abort(400, description="Auction has ended.")

    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")

    bidder = payload.get("bidder_address", "").strip()
    if not bidder:
        abort(400, description="'bidder_address' is required.")
    if bidder == trade.seller_address:
        abort(400, description="Seller cannot bid on their own auction.")

    # Validate bidder wallet exists
    wallet = Wallet.query.filter_by(address=bidder).first()
    if not wallet:
        abort(400, description="Bidder wallet not found.")

    try:
        amount = float(payload.get("amount", 0))
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        abort(400, description="'amount' must be a positive number.")

    # Bid must exceed current top bid (or the starting price if no bids yet)
    has_bids = len(trade.bids) > 0
    top_bid = max((b.amount for b in trade.bids), default=trade.price)
    if amount <= top_bid:
        label = "current top bid" if has_bids else "starting price"
        abort(400, description=f"Bid must be greater than {label} of {top_bid} {trade.currency}.")

    bid = Bid(
        trade_id=trade_id,
        bidder_address=bidder,
        amount=amount,
        currency=trade.currency,
    )
    db.session.add(bid)
    db.session.commit()
    return jsonify(bid.to_dict()), 201


@app.route("/api/trades/<int:trade_id>/accept", methods=["POST"])
def accept_trade(trade_id):
    """Accept a direct (non-auction) trade as buyer."""
    trade = db.get_or_404(Trade, trade_id)

    if trade.is_auction:
        abort(400, description="Use the bid endpoint for auction trades.")
    if trade.status != "open":
        abort(400, description="Trade is not open.")

    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")

    buyer = payload.get("buyer_address", "").strip()
    if not buyer:
        abort(400, description="'buyer_address' is required.")
    if buyer == trade.seller_address:
        abort(400, description="Seller cannot buy their own listing.")

    # Validate buyer wallet and balance
    buyer_wallet  = Wallet.query.filter_by(address=buyer).first()
    if not buyer_wallet:
        abort(400, description="Buyer wallet not found.")

    bal_attr = f"{trade.currency.lower()}_balance"
    buyer_balance = getattr(buyer_wallet, bal_attr)

    # Apply regional tax
    tax_rate = trade.region.tax_rate if trade.region else 0.0
    total_cost = trade.price * (1 + tax_rate)

    if buyer_balance < total_cost:
        abort(400, description=(
            f"Insufficient {trade.currency} balance. "
            f"Need {total_cost:.6f} (including {tax_rate*100:.1f}% regional tax)."
        ))

    seller_wallet = Wallet.query.filter_by(address=trade.seller_address).first()

    # Debit buyer, credit seller (tax is lost / burned)
    setattr(buyer_wallet,  bal_attr, buyer_balance - total_cost)
    if seller_wallet:
        seller_balance = getattr(seller_wallet, bal_attr)
        setattr(seller_wallet, bal_attr, seller_balance + trade.price)

    trade.buyer_address = buyer
    trade.status = "completed"
    trade.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify(trade.to_dict())


@app.route("/api/trades/<int:trade_id>/cancel", methods=["POST"])
def cancel_trade(trade_id):
    """Cancel an open trade (seller only)."""
    trade = db.get_or_404(Trade, trade_id)
    if trade.status != "open":
        abort(400, description="Only open trades can be cancelled.")

    payload = request.get_json(silent=True) or {}
    seller = payload.get("seller_address", "").strip()
    if seller and seller != trade.seller_address:
        abort(403, description="Only the seller can cancel this trade.")

    trade.status = "cancelled"
    trade.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(trade.to_dict())


# ──────────────────────────────────────────────────────────────────────────────
# Init
# ──────────────────────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()
    _seed_regions()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=False)
