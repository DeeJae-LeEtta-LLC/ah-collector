"""Tests for nft_collector.marketplace."""

import pytest
import responses as resp_lib

from nft_collector.marketplace import (
    OpenSeaClient,
    OpenSeaError,
    filter_listings_by_price,
    parse_floor_price,
    parse_listing_price_eth,
)

OPENSEA_BASE = "https://api.opensea.io/api/v2"


# ---------------------------------------------------------------------------
# parse_floor_price
# ---------------------------------------------------------------------------


def test_parse_floor_price_numeric():
    assert parse_floor_price({"floor_price": "1.5"}) == pytest.approx(1.5)


def test_parse_floor_price_dict():
    assert parse_floor_price({"floor_price": {"value": "2.0", "unit": "ETH"}}) == pytest.approx(2.0)


def test_parse_floor_price_missing():
    assert parse_floor_price({}) is None


# ---------------------------------------------------------------------------
# parse_listing_price_eth
# ---------------------------------------------------------------------------


def test_parse_listing_price_eth_wei_string():
    wei = 2 * 10**18
    listing = {"current_price": str(wei)}
    assert parse_listing_price_eth(listing) == pytest.approx(2.0)


def test_parse_listing_price_eth_nested():
    wei = int(0.5 * 10**18)
    listing = {"price": {"current": {"value": str(wei)}}}
    assert parse_listing_price_eth(listing) == pytest.approx(0.5)


def test_parse_listing_price_eth_missing():
    assert parse_listing_price_eth({}) is None


def test_parse_listing_price_eth_invalid():
    assert parse_listing_price_eth({"current_price": "not-a-number"}) is None


# ---------------------------------------------------------------------------
# filter_listings_by_price
# ---------------------------------------------------------------------------


def test_filter_listings_by_price_keeps_affordable():
    listings = [
        {"current_price": str(int(1.0 * 10**18))},
        {"current_price": str(int(3.0 * 10**18))},
        {"current_price": str(int(5.0 * 10**18))},
    ]
    result = filter_listings_by_price(listings, max_price_eth=3.0)
    assert len(result) == 2


def test_filter_listings_by_price_empty():
    assert filter_listings_by_price([], max_price_eth=5.0) == []


def test_filter_listings_by_price_none_above_budget():
    listings = [{"current_price": str(int(10.0 * 10**18))}]
    assert filter_listings_by_price(listings, max_price_eth=1.0) == []


# ---------------------------------------------------------------------------
# OpenSeaClient
# ---------------------------------------------------------------------------


@resp_lib.activate
def test_get_collection_stats_success():
    resp_lib.add(
        resp_lib.GET,
        f"{OPENSEA_BASE}/collections/bayc/stats",
        json={"total": {"floor_price": "5.0", "total_volume": "100000"}},
        status=200,
    )
    client = OpenSeaClient(api_key="test-key")
    stats = client.get_collection_stats("bayc")
    assert stats["floor_price"] == "5.0"


@resp_lib.activate
def test_get_collection_stats_http_error():
    resp_lib.add(
        resp_lib.GET,
        f"{OPENSEA_BASE}/collections/badslug/stats",
        json={"error": "Not Found"},
        status=404,
    )
    client = OpenSeaClient(api_key="test-key")
    with pytest.raises(OpenSeaError):
        client.get_collection_stats("badslug")


@resp_lib.activate
def test_get_best_listings_success():
    resp_lib.add(
        resp_lib.GET,
        f"{OPENSEA_BASE}/listings/collection/bayc/best",
        json={"listings": [{"order_hash": "0xabc", "current_price": str(int(5 * 10**18))}], "next": None},
        status=200,
    )
    client = OpenSeaClient(api_key="test-key")
    result = client.get_best_listings("bayc", limit=1)
    assert len(result["listings"]) == 1


@resp_lib.activate
def test_fulfill_listing_success():
    resp_lib.add(
        resp_lib.POST,
        f"{OPENSEA_BASE}/listings/fulfillment_data",
        json={"fulfillment_data": {"transaction": {"to": "0xseaport", "data": "0x", "value": "0"}}},
        status=200,
    )
    client = OpenSeaClient(api_key="test-key")
    listing = {
        "order_hash": "0xabc",
        "chain": "ethereum",
        "protocol_address": "0xseaport",
    }
    result = client.fulfill_listing(listing, "0x1234")
    assert "fulfillment_data" in result


@resp_lib.activate
def test_get_collection_success():
    resp_lib.add(
        resp_lib.GET,
        f"{OPENSEA_BASE}/collections/bayc",
        json={"collection": "bayc", "name": "Bored Ape Yacht Club"},
        status=200,
    )
    client = OpenSeaClient(api_key="test-key")
    result = client.get_collection("bayc")
    assert result["name"] == "Bored Ape Yacht Club"
