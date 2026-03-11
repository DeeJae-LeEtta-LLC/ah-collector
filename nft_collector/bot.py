"""Main NFT collector bot orchestration loop."""

import logging
import time
from typing import Any, Dict, List, Optional

from .collector import Collector, NFTItem, collection_stats_from_api
from .config import BotConfig, CollectionConfig
from .marketplace import OpenSeaClient, OpenSeaError, filter_listings_by_price, parse_listing_price_eth
from .wallet import Wallet, WalletError

logger = logging.getLogger(__name__)


class NFTCollectorBot:
    """Orchestrates NFT collection monitoring and automated buying.

    Typical usage
    -------------
    >>> config = load_config()
    >>> bot = NFTCollectorBot(config)
    >>> bot.add_collection(CollectionConfig(slug="boredapeyachtclub", name="BAYC", max_price_eth=10.0))
    >>> bot.run()          # blocking loop
    """

    def __init__(
        self,
        config: BotConfig,
        opensea_client: Optional[OpenSeaClient] = None,
        wallet: Optional[Wallet] = None,
        collector: Optional[Collector] = None,
    ) -> None:
        self._config = config
        self._client = opensea_client or OpenSeaClient(config.opensea_api_key)
        self._wallet = wallet
        self._collector = collector or Collector()
        self._running = False

        # Initialise wallet lazily — skip if ETH RPC URL is missing in dry-run
        if self._wallet is None and config.eth_rpc_url and config.wallet_address:
            try:
                self._wallet = Wallet(config.eth_rpc_url, config.wallet_address)
            except WalletError as exc:
                if not config.dry_run:
                    raise
                logger.warning("Wallet not available (dry-run mode): %s", exc)

    # ------------------------------------------------------------------ #
    # Collection management                                                #
    # ------------------------------------------------------------------ #

    def add_collection(self, collection_config: CollectionConfig) -> None:
        """Register a collection for monitoring."""
        self._config.collections.append(collection_config)
        logger.info("Watching collection: %s (max %.4f ETH)", collection_config.slug, collection_config.max_price_eth)

    # ------------------------------------------------------------------ #
    # Core loop                                                            #
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        """Start the monitoring loop (blocks indefinitely)."""
        logger.info(
            "NFT collector bot starting. dry_run=%s, %d collection(s) watched.",
            self._config.dry_run,
            len(self._config.collections),
        )
        self._running = True
        try:
            while self._running:
                self._tick()
                time.sleep(self._config.check_interval_seconds)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user.")
        finally:
            self._running = False

    def stop(self) -> None:
        """Signal the monitoring loop to stop after the current tick."""
        self._running = False

    def tick(self) -> List[Dict[str, Any]]:
        """Run one monitoring cycle and return a list of action records."""
        return self._tick()

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _tick(self) -> List[Dict[str, Any]]:
        """Check each watched collection once and take action if warranted."""
        actions: List[Dict[str, Any]] = []
        for col_cfg in self._config.collections:
            try:
                action = self._process_collection(col_cfg)
                if action:
                    actions.append(action)
            except Exception as exc:
                logger.error("Error processing collection %s: %s", col_cfg.slug, exc)
        return actions

    def _process_collection(self, col_cfg: CollectionConfig) -> Optional[Dict[str, Any]]:
        """Check one collection and optionally purchase an NFT."""
        # 1. Fetch and record stats
        raw_stats = self._client.get_collection_stats(col_cfg.slug)
        stats = collection_stats_from_api(col_cfg.slug, raw_stats)
        self._collector.record_stats(stats)

        floor = stats.floor_price_eth
        logger.info(
            "[%s] floor=%.4f ETH (max=%.4f ETH)",
            col_cfg.slug,
            floor if floor is not None else 0.0,
            col_cfg.max_price_eth,
        )

        # 2. Skip if floor is above our threshold
        if floor is None or floor > col_cfg.max_price_eth:
            return None

        if not col_cfg.auto_buy:
            logger.info("[%s] Floor is within budget but auto_buy is disabled.", col_cfg.slug)
            return {"collection": col_cfg.slug, "action": "skip", "reason": "auto_buy disabled", "floor_price_eth": floor}

        # 3. Find the best listing within budget
        listing = self._find_best_listing(col_cfg)
        if listing is None:
            return None

        price = parse_listing_price_eth(listing)

        # 4. Check wallet balance (if wallet is available)
        if self._wallet is not None:
            if not self._wallet.has_sufficient_balance(price or col_cfg.max_price_eth):
                logger.warning("[%s] Insufficient wallet balance to buy.", col_cfg.slug)
                return {"collection": col_cfg.slug, "action": "skip", "reason": "insufficient_balance", "floor_price_eth": floor}

            # 5. Check gas price
            try:
                gas_gwei = self._wallet.get_gas_price_gwei()
                if gas_gwei > self._config.max_gas_gwei:
                    logger.warning(
                        "[%s] Gas too high: %.1f Gwei (max=%.1f)", col_cfg.slug, gas_gwei, self._config.max_gas_gwei
                    )
                    return {"collection": col_cfg.slug, "action": "skip", "reason": "gas_too_high", "gas_gwei": gas_gwei}
            except WalletError as exc:
                logger.warning("[%s] Could not check gas price: %s", col_cfg.slug, exc)

        # 6. Execute purchase
        return self._execute_purchase(col_cfg, listing, price or col_cfg.max_price_eth)

    def _find_best_listing(self, col_cfg: CollectionConfig) -> Optional[Dict[str, Any]]:
        """Return the cheapest listing that meets the collection criteria."""
        try:
            data = self._client.get_best_listings(col_cfg.slug, limit=10)
        except OpenSeaError as exc:
            logger.error("[%s] Failed to fetch listings: %s", col_cfg.slug, exc)
            return None

        listings = data.get("listings", [])
        affordable = filter_listings_by_price(listings, col_cfg.max_price_eth)

        if col_cfg.required_traits:
            affordable = [l for l in affordable if _matches_traits(l, col_cfg.required_traits)]

        if not affordable:
            return None

        # Return the cheapest one
        return min(affordable, key=lambda l: parse_listing_price_eth(l) or float("inf"))

    def _execute_purchase(
        self,
        col_cfg: CollectionConfig,
        listing: Dict[str, Any],
        price_eth: float,
    ) -> Dict[str, Any]:
        """Fulfil a listing (or simulate in dry-run mode)."""
        token_id = listing.get("token_identifier") or listing.get("token_id", "unknown")
        contract = listing.get("asset_contract_address") or listing.get("contract", "")

        if self._config.dry_run:
            logger.info(
                "[DRY RUN] Would buy %s #%s for %.4f ETH", col_cfg.slug, token_id, price_eth
            )
            return {
                "collection": col_cfg.slug,
                "action": "dry_run_buy",
                "token_id": token_id,
                "price_eth": price_eth,
            }

        # Real purchase
        try:
            fulfillment = self._client.fulfill_listing(listing, self._config.wallet_address)
            tx_data = fulfillment.get("fulfillment_data", {}).get("transaction", {})
            tx_hash = self._wallet.send_transaction(tx_data)
            logger.info("[%s] Purchased #%s tx=%s (%.4f ETH)", col_cfg.slug, token_id, tx_hash, price_eth)

            self._collector.add_nft(
                NFTItem(
                    contract_address=contract,
                    token_id=str(token_id),
                    collection_slug=col_cfg.slug,
                    name=f"{col_cfg.name} #{token_id}",
                    purchase_price_eth=price_eth,
                    purchase_tx_hash=tx_hash,
                )
            )
            return {
                "collection": col_cfg.slug,
                "action": "bought",
                "token_id": token_id,
                "price_eth": price_eth,
                "tx_hash": tx_hash,
            }
        except (OpenSeaError, WalletError) as exc:
            logger.error("[%s] Purchase failed: %s", col_cfg.slug, exc)
            return {"collection": col_cfg.slug, "action": "error", "error": str(exc)}

    @property
    def collector(self) -> Collector:
        """Expose the underlying collector for inspection."""
        return self._collector


def _matches_traits(listing: Dict[str, Any], required_traits: dict) -> bool:
    """Return True if a listing's NFT has all the required trait values."""
    traits = listing.get("nft", {}).get("traits", [])
    trait_map = {t.get("trait_type"): t.get("value") for t in traits}
    for trait_type, expected_value in required_traits.items():
        if trait_map.get(trait_type) != expected_value:
            return False
    return True
