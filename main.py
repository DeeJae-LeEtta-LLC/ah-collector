"""
AH Collector - Auction House Collector Application
Flask backend providing REST API and serving the frontend.
Includes the DeeJaeLeEtta Network: cryptocurrency funnels for onboarding
customers, employees, and investors.
"""

import os
import re
import json
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
# DeeJaeLeEtta Network Models
# ──────────────────────────────────────────────────────────────────────────────

CRYPTO_CHOICES = [
    "Bitcoin (BTC)", "Ethereum (ETH)", "Solana (SOL)", "Binance Coin (BNB)",
    "Cardano (ADA)", "Polygon (MATIC)", "Avalanche (AVAX)", "Other",
]

INVESTMENT_RANGE_CHOICES = [
    "Under $1,000", "$1,000 – $9,999", "$10,000 – $49,999",
    "$50,000 – $249,999", "$250,000+",
]


class NetworkCustomer(db.Model):
    """Onboarded customer collected via the DeeJaeLeEtta Network funnel."""

    __tablename__ = "network_customers"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    wallet_address = db.Column(db.String(200), nullable=True)
    preferred_crypto = db.Column(db.String(100), nullable=True)
    investment_interests = db.Column(db.String(500), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "wallet_address": self.wallet_address,
            "preferred_crypto": self.preferred_crypto,
            "investment_interests": self.investment_interests,
            "country": self.country,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class NetworkEmployee(db.Model):
    """Onboarded employee collected via the DeeJaeLeEtta Network funnel."""

    __tablename__ = "network_employees"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    role = db.Column(db.String(200), nullable=True)
    skills = db.Column(db.String(500), nullable=True)
    portfolio_url = db.Column(db.String(500), nullable=True)
    availability = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "role": self.role,
            "skills": self.skills,
            "portfolio_url": self.portfolio_url,
            "availability": self.availability,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class NetworkInvestor(db.Model):
    """Onboarded investor collected via the DeeJaeLeEtta Network funnel."""

    __tablename__ = "network_investors"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    wallet_address = db.Column(db.String(200), nullable=True)
    investment_range = db.Column(db.String(100), nullable=True)
    investment_type = db.Column(db.String(200), nullable=True)
    experience_level = db.Column(db.String(100), nullable=True)
    is_accredited = db.Column(db.Boolean, default=False)
    preferred_crypto = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "wallet_address": self.wallet_address,
            "investment_range": self.investment_range,
            "investment_type": self.investment_type,
            "experience_level": self.experience_level,
            "is_accredited": self.is_accredited,
            "preferred_crypto": self.preferred_crypto,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Frontend routes
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main dashboard."""
    return render_template("index.html")


@app.route("/network")
def network():
    """Serve the DeeJaeLeEtta Network admin dashboard."""
    return render_template("network.html")


@app.route("/onboard")
def onboard():
    """Serve the public-facing onboarding funnel (defaults to customer tab)."""
    return render_template("onboard.html", crypto_choices=CRYPTO_CHOICES,
                           investment_range_choices=INVESTMENT_RANGE_CHOICES)


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
# DeeJaeLeEtta Network API routes
# ──────────────────────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+$")


def _validate_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email))


@app.route("/api/network/stats", methods=["GET"])
def network_stats():
    """Return summary statistics for the DeeJaeLeEtta Network."""
    return jsonify({
        "total_customers": NetworkCustomer.query.count(),
        "total_employees": NetworkEmployee.query.count(),
        "total_investors": NetworkInvestor.query.count(),
    })


@app.route("/api/network/customers", methods=["GET"])
def list_network_customers():
    """List all onboarded customers."""
    customers = NetworkCustomer.query.order_by(desc(NetworkCustomer.created_at)).all()
    return jsonify([c.to_dict() for c in customers])


@app.route("/api/network/employees", methods=["GET"])
def list_network_employees():
    """List all onboarded employees."""
    employees = NetworkEmployee.query.order_by(desc(NetworkEmployee.created_at)).all()
    return jsonify([e.to_dict() for e in employees])


@app.route("/api/network/investors", methods=["GET"])
def list_network_investors():
    """List all onboarded investors."""
    investors = NetworkInvestor.query.order_by(desc(NetworkInvestor.created_at)).all()
    return jsonify([i.to_dict() for i in investors])


@app.route("/api/onboard/customer", methods=["POST"])
def onboard_customer():
    """Submit a customer onboarding form."""
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")

    full_name = payload.get("full_name", "").strip()
    if not full_name:
        abort(400, description="'full_name' is required.")

    email = payload.get("email", "").strip().lower()
    if not email or not _validate_email(email):
        abort(400, description="A valid 'email' is required.")

    customer = NetworkCustomer(
        full_name=full_name,
        email=email,
        phone=payload.get("phone", "").strip() or None,
        wallet_address=payload.get("wallet_address", "").strip() or None,
        preferred_crypto=payload.get("preferred_crypto", "").strip() or None,
        investment_interests=payload.get("investment_interests", "").strip() or None,
        country=payload.get("country", "").strip() or None,
        notes=payload.get("notes", "").strip() or None,
    )
    db.session.add(customer)
    db.session.commit()
    return jsonify(customer.to_dict()), 201


@app.route("/api/onboard/employee", methods=["POST"])
def onboard_employee():
    """Submit an employee onboarding form."""
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")

    full_name = payload.get("full_name", "").strip()
    if not full_name:
        abort(400, description="'full_name' is required.")

    email = payload.get("email", "").strip().lower()
    if not email or not _validate_email(email):
        abort(400, description="A valid 'email' is required.")

    employee = NetworkEmployee(
        full_name=full_name,
        email=email,
        phone=payload.get("phone", "").strip() or None,
        role=payload.get("role", "").strip() or None,
        skills=payload.get("skills", "").strip() or None,
        portfolio_url=payload.get("portfolio_url", "").strip() or None,
        availability=payload.get("availability", "").strip() or None,
        notes=payload.get("notes", "").strip() or None,
    )
    db.session.add(employee)
    db.session.commit()
    return jsonify(employee.to_dict()), 201


@app.route("/api/onboard/investor", methods=["POST"])
def onboard_investor():
    """Submit an investor onboarding form."""
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")

    full_name = payload.get("full_name", "").strip()
    if not full_name:
        abort(400, description="'full_name' is required.")

    email = payload.get("email", "").strip().lower()
    if not email or not _validate_email(email):
        abort(400, description="A valid 'email' is required.")

    investor = NetworkInvestor(
        full_name=full_name,
        email=email,
        phone=payload.get("phone", "").strip() or None,
        wallet_address=payload.get("wallet_address", "").strip() or None,
        investment_range=payload.get("investment_range", "").strip() or None,
        investment_type=payload.get("investment_type", "").strip() or None,
        experience_level=payload.get("experience_level", "").strip() or None,
        is_accredited=bool(payload.get("is_accredited", False)),
        preferred_crypto=payload.get("preferred_crypto", "").strip() or None,
        notes=payload.get("notes", "").strip() or None,
    )
    db.session.add(investor)
    db.session.commit()
    return jsonify(investor.to_dict()), 201


# ──────────────────────────────────────────────────────────────────────────────
# Init
# ──────────────────────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=False)
