"""
AH Collector - Auction House Collector Application
Flask backend providing REST API and serving the frontend.
"""

import os
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


class EmailContact(db.Model):
    """Stores email contacts for the call log."""

    __tablename__ = "email_contacts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Frontend routes
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main dashboard."""
    return render_template("index.html")


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


@app.route("/api/emails", methods=["GET"])
def get_emails():
    """Return all email contacts, with optional search."""
    search = request.args.get("search", "").strip()

    query = EmailContact.query

    if search:
        query = query.filter(
            EmailContact.name.ilike(f"%{search}%")
            | EmailContact.email.ilike(f"%{search}%")
        )

    contacts = query.order_by(desc(EmailContact.updated_at)).all()
    return jsonify([c.to_dict() for c in contacts])


@app.route("/api/emails/<int:contact_id>", methods=["GET"])
def get_email(contact_id):
    """Return a single email contact."""
    contact = db.get_or_404(EmailContact, contact_id)
    return jsonify(contact.to_dict())


@app.route("/api/emails", methods=["POST"])
def create_email():
    """Create a new email contact."""
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")

    name = payload.get("name", "").strip()
    if not name:
        abort(400, description="'name' is required.")

    email = payload.get("email", "").strip()
    if not email:
        abort(400, description="'email' is required.")

    contact = EmailContact(
        name=name,
        email=email,
        phone=payload.get("phone", "").strip() or None,
        notes=payload.get("notes", "").strip() or None,
    )
    db.session.add(contact)
    db.session.commit()
    return jsonify(contact.to_dict()), 201


@app.route("/api/emails/<int:contact_id>", methods=["PUT"])
def update_email(contact_id):
    """Update an existing email contact."""
    contact = db.get_or_404(EmailContact, contact_id)
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")

    if "name" in payload:
        name = payload["name"].strip()
        if not name:
            abort(400, description="'name' cannot be empty.")
        contact.name = name

    if "email" in payload:
        email = payload["email"].strip()
        if not email:
            abort(400, description="'email' cannot be empty.")
        contact.email = email

    if "phone" in payload:
        contact.phone = payload["phone"].strip() or None
    if "notes" in payload:
        contact.notes = payload["notes"].strip() or None

    contact.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(contact.to_dict())


@app.route("/api/emails/<int:contact_id>", methods=["DELETE"])
def delete_email(contact_id):
    """Delete an email contact."""
    contact = db.get_or_404(EmailContact, contact_id)
    db.session.delete(contact)
    db.session.commit()
    return jsonify({"message": f"Contact {contact_id} deleted."})


# ──────────────────────────────────────────────────────────────────────────────
# Init
# ──────────────────────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=False)
