"""Tests for nft_collector.collector."""

from datetime import datetime, timezone

import pytest

from nft_collector.collector import (
    Collector,
    CollectionStats,
    NFTItem,
    collection_stats_from_api,
)


def _make_item(token_id: str = "1", price: float = 1.0) -> NFTItem:
    return NFTItem(
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        token_id=token_id,
        collection_slug="bayc",
        name=f"BAYC #{token_id}",
        purchase_price_eth=price,
        purchase_tx_hash="0xtx" + token_id,
    )


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


def test_add_and_get_nfts():
    col = Collector()
    item = _make_item("42", 2.5)
    col.add_nft(item)
    owned = col.get_owned_nfts()
    assert len(owned) == 1
    assert owned[0].token_id == "42"


def test_get_nfts_filtered_by_collection():
    col = Collector()
    col.add_nft(_make_item("1"))
    other = NFTItem(
        contract_address="0xother",
        token_id="99",
        collection_slug="other-collection",
        name="Other #99",
        purchase_price_eth=0.5,
        purchase_tx_hash="0xtx99",
    )
    col.add_nft(other)
    assert len(col.get_owned_nfts("bayc")) == 1
    assert len(col.get_owned_nfts("other-collection")) == 1
    assert len(col.get_owned_nfts()) == 2


def test_total_spent_eth():
    col = Collector()
    col.add_nft(_make_item("1", price=1.0))
    col.add_nft(_make_item("2", price=2.5))
    assert col.total_spent_eth() == pytest.approx(3.5)


def test_total_spent_eth_empty():
    assert Collector().total_spent_eth() == 0.0


# ---------------------------------------------------------------------------
# Stats history
# ---------------------------------------------------------------------------


def test_record_and_latest_stats():
    col = Collector()
    stats = CollectionStats(slug="bayc", floor_price_eth=5.0, total_volume_eth=100.0, num_owners=10, total_supply=10000)
    col.record_stats(stats)
    assert col.latest_stats("bayc") == stats


def test_latest_stats_missing():
    assert Collector().latest_stats("unknown") is None


def test_stats_history_ordered():
    col = Collector()
    s1 = CollectionStats(slug="bayc", floor_price_eth=5.0, total_volume_eth=100.0, num_owners=None, total_supply=None)
    s2 = CollectionStats(slug="bayc", floor_price_eth=4.8, total_volume_eth=101.0, num_owners=None, total_supply=None)
    col.record_stats(s1)
    col.record_stats(s2)
    history = col.stats_history("bayc")
    assert len(history) == 2
    assert history[-1].floor_price_eth == pytest.approx(4.8)


# ---------------------------------------------------------------------------
# portfolio_summary
# ---------------------------------------------------------------------------


def test_portfolio_summary_empty():
    summary = Collector().portfolio_summary()
    assert summary["total_nfts"] == 0
    assert summary["total_spent_eth"] == 0.0
    assert summary["collections"] == {}


def test_portfolio_summary_with_items():
    col = Collector()
    col.add_nft(_make_item("1", 2.0))
    col.add_nft(_make_item("2", 3.0))
    summary = col.portfolio_summary()
    assert summary["total_nfts"] == 2
    assert summary["total_spent_eth"] == pytest.approx(5.0)
    assert "bayc" in summary["collections"]
    assert summary["collections"]["bayc"]["count"] == 2


# ---------------------------------------------------------------------------
# collection_stats_from_api
# ---------------------------------------------------------------------------


def test_collection_stats_from_api_plain_floor():
    api = {"floor_price": "5.0", "total_volume": "1000.0", "num_owners": 5000, "total_supply": 10000}
    stats = collection_stats_from_api("bayc", api)
    assert stats.floor_price_eth == pytest.approx(5.0)
    assert stats.total_volume_eth == pytest.approx(1000.0)
    assert stats.num_owners == 5000
    assert stats.total_supply == 10000


def test_collection_stats_from_api_dict_floor():
    api = {"floor_price": {"value": "3.5", "unit": "ETH"}, "total_volume": {"value": "500.0"}}
    stats = collection_stats_from_api("bayc", api)
    assert stats.floor_price_eth == pytest.approx(3.5)
    assert stats.total_volume_eth == pytest.approx(500.0)


def test_collection_stats_from_api_missing_floor():
    stats = collection_stats_from_api("bayc", {})
    assert stats.floor_price_eth is None
