"""NFT collection and portfolio tracker."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class NFTItem:
    """Represents a single collected NFT."""

    contract_address: str
    token_id: str
    collection_slug: str
    name: str
    purchase_price_eth: float
    purchase_tx_hash: str
    acquired_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    traits: Dict[str, Any] = field(default_factory=dict)
    image_url: Optional[str] = None


@dataclass
class CollectionStats:
    """Snapshot of a collection's current stats."""

    slug: str
    floor_price_eth: Optional[float]
    total_volume_eth: Optional[float]
    num_owners: Optional[int]
    total_supply: Optional[int]
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class Collector:
    """Tracks watched collections and owned NFTs."""

    def __init__(self) -> None:
        self._owned: List[NFTItem] = []
        self._collection_stats: Dict[str, List[CollectionStats]] = {}

    # ------------------------------------------------------------------ #
    # Portfolio                                                            #
    # ------------------------------------------------------------------ #

    def add_nft(self, item: NFTItem) -> None:
        """Record a newly acquired NFT."""
        self._owned.append(item)
        logger.info(
            "Added NFT %s #%s to portfolio (paid %.4f ETH)",
            item.collection_slug,
            item.token_id,
            item.purchase_price_eth,
        )

    def get_owned_nfts(self, collection_slug: Optional[str] = None) -> List[NFTItem]:
        """Return owned NFTs, optionally filtered by collection."""
        if collection_slug is None:
            return list(self._owned)
        return [n for n in self._owned if n.collection_slug == collection_slug]

    def total_spent_eth(self) -> float:
        """Return the total ETH spent on collected NFTs."""
        return sum(n.purchase_price_eth for n in self._owned)

    # ------------------------------------------------------------------ #
    # Stats history                                                        #
    # ------------------------------------------------------------------ #

    def record_stats(self, stats: CollectionStats) -> None:
        """Store a stats snapshot for a collection."""
        history = self._collection_stats.setdefault(stats.slug, [])
        history.append(stats)

    def latest_stats(self, collection_slug: str) -> Optional[CollectionStats]:
        """Return the most recent stats snapshot for a collection, or None."""
        history = self._collection_stats.get(collection_slug)
        if not history:
            return None
        return history[-1]

    def stats_history(self, collection_slug: str) -> List[CollectionStats]:
        """Return all stored stats snapshots for a collection."""
        return list(self._collection_stats.get(collection_slug, []))

    # ------------------------------------------------------------------ #
    # Serialisation helpers                                                #
    # ------------------------------------------------------------------ #

    def portfolio_summary(self) -> Dict[str, Any]:
        """Return a JSON-serialisable summary of the portfolio."""
        return {
            "total_nfts": len(self._owned),
            "total_spent_eth": self.total_spent_eth(),
            "collections": _group_by_collection(self._owned),
        }


def _group_by_collection(items: List[NFTItem]) -> Dict[str, Any]:
    groups: Dict[str, Any] = {}
    for item in items:
        slug = item.collection_slug
        entry = groups.setdefault(slug, {"count": 0, "total_spent_eth": 0.0, "items": []})
        entry["count"] += 1
        entry["total_spent_eth"] += item.purchase_price_eth
        entry["items"].append(
            {
                "token_id": item.token_id,
                "contract_address": item.contract_address,
                "name": item.name,
                "purchase_price_eth": item.purchase_price_eth,
                "purchase_tx_hash": item.purchase_tx_hash,
                "acquired_at": item.acquired_at.isoformat(),
            }
        )
    return groups


def collection_stats_from_api(slug: str, api_stats: Dict[str, Any]) -> CollectionStats:
    """Convert raw OpenSea stats API response into a CollectionStats object."""
    floor = api_stats.get("floor_price")
    if isinstance(floor, dict):
        floor = float(floor.get("value", 0) or 0)
    elif floor is not None:
        floor = float(floor)

    volume = api_stats.get("total_volume")
    if isinstance(volume, dict):
        volume = float(volume.get("value", 0) or 0)
    elif volume is not None:
        volume = float(volume)

    return CollectionStats(
        slug=slug,
        floor_price_eth=floor,
        total_volume_eth=volume,
        num_owners=api_stats.get("num_owners"),
        total_supply=api_stats.get("total_supply"),
    )
