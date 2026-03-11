"""Configuration management for the NFT collector bot."""

import os
from dataclasses import dataclass, field
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class CollectionConfig:
    """Configuration for a single NFT collection to monitor."""

    slug: str
    name: str
    max_price_eth: float
    auto_buy: bool = False
    min_rarity_rank: Optional[int] = None
    max_rarity_rank: Optional[int] = None
    required_traits: Optional[dict] = None

    def __post_init__(self) -> None:
        if self.max_price_eth <= 0:
            raise ValueError("max_price_eth must be positive")
        if self.min_rarity_rank is not None and self.min_rarity_rank < 1:
            raise ValueError("min_rarity_rank must be >= 1")
        if (
            self.min_rarity_rank is not None
            and self.max_rarity_rank is not None
            and self.min_rarity_rank > self.max_rarity_rank
        ):
            raise ValueError("min_rarity_rank must be <= max_rarity_rank")


@dataclass
class BotConfig:
    """Main bot configuration."""

    opensea_api_key: str
    wallet_address: str
    eth_rpc_url: str
    collections: List[CollectionConfig] = field(default_factory=list)
    check_interval_seconds: int = 60
    network: str = "ethereum"
    dry_run: bool = True
    max_gas_gwei: float = 50.0

    def __post_init__(self) -> None:
        if not self.opensea_api_key:
            raise ValueError("opensea_api_key is required")
        if not self.wallet_address:
            raise ValueError("wallet_address is required")
        if self.check_interval_seconds < 10:
            raise ValueError("check_interval_seconds must be >= 10")
        if self.max_gas_gwei <= 0:
            raise ValueError("max_gas_gwei must be positive")


def load_config() -> BotConfig:
    """Load bot configuration from environment variables."""
    opensea_api_key = os.environ.get("OPENSEA_API_KEY", "")
    wallet_address = os.environ.get("WALLET_ADDRESS", "")
    eth_rpc_url = os.environ.get("ETH_RPC_URL", "https://eth.llamarpc.com")
    dry_run = os.environ.get("DRY_RUN", "true").lower() != "false"
    check_interval = int(os.environ.get("CHECK_INTERVAL_SECONDS", "60"))
    max_gas_gwei = float(os.environ.get("MAX_GAS_GWEI", "50.0"))
    network = os.environ.get("NETWORK", "ethereum")

    return BotConfig(
        opensea_api_key=opensea_api_key,
        wallet_address=wallet_address,
        eth_rpc_url=eth_rpc_url,
        dry_run=dry_run,
        check_interval_seconds=check_interval,
        max_gas_gwei=max_gas_gwei,
        network=network,
    )
