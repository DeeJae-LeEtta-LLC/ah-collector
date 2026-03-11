"""Shared pytest fixtures."""

import pytest

from nft_collector.config import BotConfig, CollectionConfig


@pytest.fixture()
def base_config() -> BotConfig:
    """Minimal BotConfig with dry_run=True."""
    return BotConfig(
        opensea_api_key="test-api-key",
        wallet_address="0x1234567890123456789012345678901234567890",
        eth_rpc_url="https://eth.llamarpc.com",
        dry_run=True,
    )


@pytest.fixture()
def bayc_collection() -> CollectionConfig:
    """Sample CollectionConfig for testing."""
    return CollectionConfig(
        slug="boredapeyachtclub",
        name="BAYC",
        max_price_eth=10.0,
        auto_buy=True,
    )


@pytest.fixture()
def sample_listing() -> dict:
    """A minimal OpenSea v2-style listing object."""
    return {
        "order_hash": "0xabc123",
        "protocol_address": "0xseaport",
        "chain": "ethereum",
        "asset_contract_address": "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        "token_identifier": "1234",
        "current_price": str(5 * 10**18),  # 5 ETH in wei
    }
