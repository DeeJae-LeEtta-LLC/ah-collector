"""Flask web API entry point for the NFT collector bot."""

import logging
import os
import threading
from typing import Any, Dict

from flask import Flask, jsonify, request

from nft_collector.bot import NFTCollectorBot
from nft_collector.collector import Collector
from nft_collector.config import BotConfig, CollectionConfig, load_config
from nft_collector.marketplace import OpenSeaClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global bot instance and background thread
_bot: NFTCollectorBot | None = None
_bot_thread: threading.Thread | None = None


def _get_bot() -> NFTCollectorBot:
    global _bot
    if _bot is None:
        cfg = load_config()
        _bot = NFTCollectorBot(cfg)
    return _bot


# ------------------------------------------------------------------ #
# Routes                                                               #
# ------------------------------------------------------------------ #


@app.route("/health", methods=["GET"])
def health() -> tuple[Any, int]:
    """Health-check endpoint."""
    return jsonify({"status": "ok"}), 200


@app.route("/status", methods=["GET"])
def status() -> tuple[Any, int]:
    """Return bot status and portfolio summary."""
    bot = _get_bot()
    summary = bot.collector.portfolio_summary()
    return jsonify(
        {
            "running": _bot_thread is not None and _bot_thread.is_alive(),
            "dry_run": bot._config.dry_run,
            "collections_watched": len(bot._config.collections),
            "portfolio": summary,
        }
    ), 200


@app.route("/collections", methods=["GET"])
def list_collections() -> tuple[Any, int]:
    """List all watched collections."""
    bot = _get_bot()
    collections = [
        {
            "slug": c.slug,
            "name": c.name,
            "max_price_eth": c.max_price_eth,
            "auto_buy": c.auto_buy,
        }
        for c in bot._config.collections
    ]
    return jsonify({"collections": collections}), 200


@app.route("/collections", methods=["POST"])
def add_collection() -> tuple[Any, int]:
    """Add a collection to watch.

    JSON body::

        {
            "slug": "boredapeyachtclub",
            "name": "BAYC",
            "max_price_eth": 5.0,
            "auto_buy": false
        }
    """
    data: Dict[str, Any] = request.get_json(force=True) or {}
    try:
        col = CollectionConfig(
            slug=data["slug"],
            name=data.get("name", data["slug"]),
            max_price_eth=float(data["max_price_eth"]),
            auto_buy=bool(data.get("auto_buy", False)),
        )
    except (KeyError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    bot = _get_bot()
    bot.add_collection(col)
    return jsonify({"message": f"Watching {col.slug}"}), 201


@app.route("/portfolio", methods=["GET"])
def portfolio() -> tuple[Any, int]:
    """Return the current portfolio summary."""
    bot = _get_bot()
    return jsonify(bot.collector.portfolio_summary()), 200


@app.route("/tick", methods=["POST"])
def manual_tick() -> tuple[Any, int]:
    """Manually trigger one monitoring cycle."""
    bot = _get_bot()
    actions = bot.tick()
    return jsonify({"actions": actions}), 200


@app.route("/start", methods=["POST"])
def start_bot() -> tuple[Any, int]:
    """Start the background monitoring loop."""
    global _bot_thread
    if _bot_thread is not None and _bot_thread.is_alive():
        return jsonify({"message": "Bot already running"}), 200

    bot = _get_bot()

    def _run() -> None:
        bot.run()

    _bot_thread = threading.Thread(target=_run, name="nft-collector-bot", daemon=True)
    _bot_thread.start()
    return jsonify({"message": "Bot started"}), 200


@app.route("/stop", methods=["POST"])
def stop_bot() -> tuple[Any, int]:
    """Stop the background monitoring loop."""
    bot = _get_bot()
    bot.stop()
    return jsonify({"message": "Stop signal sent"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)
