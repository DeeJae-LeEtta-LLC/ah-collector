"""Tests for nft_collector.bot (NFTCollectorBot)."""

from unittest.mock import MagicMock, patch

import pytest

from nft_collector.bot import NFTCollectorBot, _matches_traits
from nft_collector.collector import Collector
from nft_collector.config import BotConfig, CollectionConfig
from nft_collector.marketplace import OpenSeaClient


def _bot(dry_run: bool = True, collections=None) -> NFTCollectorBot:
    config = BotConfig(
        opensea_api_key="key",
        wallet_address="0x1234567890123456789012345678901234567890",
        eth_rpc_url="",
        dry_run=dry_run,
        collections=collections or [],
    )
    client = MagicMock(spec=OpenSeaClient)
    collector = Collector()
    return NFTCollectorBot(config, opensea_client=client, wallet=None, collector=collector)


def _cheap_listing(price_eth: float = 1.0) -> dict:
    return {
        "order_hash": "0xabc",
        "chain": "ethereum",
        "protocol_address": "0xseaport",
        "asset_contract_address": "0xcontract",
        "token_identifier": "42",
        "current_price": str(int(price_eth * 10**18)),
    }


# ---------------------------------------------------------------------------
# add_collection
# ---------------------------------------------------------------------------


def test_add_collection():
    bot = _bot()
    col = CollectionConfig(slug="bayc", name="BAYC", max_price_eth=5.0)
    bot.add_collection(col)
    assert len(bot._config.collections) == 1


# ---------------------------------------------------------------------------
# _matches_traits
# ---------------------------------------------------------------------------


def test_matches_traits_all_match():
    listing = {
        "nft": {
            "traits": [
                {"trait_type": "Background", "value": "Blue"},
                {"trait_type": "Eyes", "value": "Bored"},
            ]
        }
    }
    assert _matches_traits(listing, {"Background": "Blue", "Eyes": "Bored"})


def test_matches_traits_partial_miss():
    listing = {"nft": {"traits": [{"trait_type": "Background", "value": "Blue"}]}}
    assert not _matches_traits(listing, {"Background": "Blue", "Eyes": "Laser"})


def test_matches_traits_empty_required():
    assert _matches_traits({}, {})


# ---------------------------------------------------------------------------
# _process_collection — floor above budget
# ---------------------------------------------------------------------------


def test_process_collection_floor_above_budget():
    bot = _bot()
    bot._client.get_collection_stats.return_value = {"floor_price": "100.0"}
    col = CollectionConfig(slug="bayc", name="BAYC", max_price_eth=5.0, auto_buy=True)
    result = bot._process_collection(col)
    assert result is None
    # Should NOT attempt to fetch listings
    bot._client.get_best_listings.assert_not_called()


# ---------------------------------------------------------------------------
# _process_collection — auto_buy disabled
# ---------------------------------------------------------------------------


def test_process_collection_auto_buy_disabled():
    bot = _bot()
    bot._client.get_collection_stats.return_value = {"floor_price": "1.0"}
    col = CollectionConfig(slug="bayc", name="BAYC", max_price_eth=5.0, auto_buy=False)
    result = bot._process_collection(col)
    assert result is not None
    assert result["action"] == "skip"
    assert result["reason"] == "auto_buy disabled"


# ---------------------------------------------------------------------------
# _process_collection — no affordable listings
# ---------------------------------------------------------------------------


def test_process_collection_no_affordable_listings():
    bot = _bot()
    bot._client.get_collection_stats.return_value = {"floor_price": "2.0"}
    # All listings are above budget
    bot._client.get_best_listings.return_value = {
        "listings": [_cheap_listing(price_eth=10.0)],
        "next": None,
    }
    col = CollectionConfig(slug="bayc", name="BAYC", max_price_eth=5.0, auto_buy=True)
    result = bot._process_collection(col)
    assert result is None


# ---------------------------------------------------------------------------
# _process_collection — dry-run buy
# ---------------------------------------------------------------------------


def test_process_collection_dry_run_buy():
    bot = _bot(dry_run=True)
    bot._client.get_collection_stats.return_value = {"floor_price": "1.0"}
    bot._client.get_best_listings.return_value = {
        "listings": [_cheap_listing(price_eth=1.0)],
        "next": None,
    }
    col = CollectionConfig(slug="bayc", name="BAYC", max_price_eth=5.0, auto_buy=True)
    result = bot._process_collection(col)
    assert result is not None
    assert result["action"] == "dry_run_buy"
    assert result["price_eth"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# tick — processes all collections
# ---------------------------------------------------------------------------


def test_tick_processes_all_collections():
    col1 = CollectionConfig(slug="bayc", name="BAYC", max_price_eth=5.0, auto_buy=False)
    col2 = CollectionConfig(slug="cryptopunks", name="Punks", max_price_eth=10.0, auto_buy=False)
    bot = _bot(collections=[col1, col2])
    bot._client.get_collection_stats.return_value = {"floor_price": "1.0"}
    actions = bot.tick()
    assert bot._client.get_collection_stats.call_count == 2
    assert len(actions) == 2  # both should return "skip" actions


# ---------------------------------------------------------------------------
# tick — errors in one collection don't break others
# ---------------------------------------------------------------------------


def test_tick_continues_on_error():
    col1 = CollectionConfig(slug="bayc", name="BAYC", max_price_eth=5.0, auto_buy=False)
    col2 = CollectionConfig(slug="cryptopunks", name="Punks", max_price_eth=10.0, auto_buy=False)
    bot = _bot(collections=[col1, col2])
    # First call raises, second succeeds
    bot._client.get_collection_stats.side_effect = [
        Exception("API down"),
        {"floor_price": "1.0"},
    ]
    actions = bot.tick()
    # Only the second collection should produce an action
    assert len(actions) == 1
    assert actions[0]["collection"] == "cryptopunks"


# ---------------------------------------------------------------------------
# Collector property
# ---------------------------------------------------------------------------


def test_collector_property():
    bot = _bot()
    assert isinstance(bot.collector, Collector)
