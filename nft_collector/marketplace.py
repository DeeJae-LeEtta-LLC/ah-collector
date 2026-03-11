"""OpenSea API v2 client for the NFT collector bot."""

import logging
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

OPENSEA_BASE_URL = "https://api.opensea.io/api/v2"
REQUEST_TIMEOUT = 30


class OpenSeaError(Exception):
    """Raised when an OpenSea API request fails."""


class OpenSeaClient:
    """Client for interacting with the OpenSea API v2."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-API-KEY": api_key,
                "Accept": "application/json",
            }
        )

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform a GET request against the OpenSea API."""
        url = f"{OPENSEA_BASE_URL}/{path.lstrip('/')}"
        try:
            response = self._session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            raise OpenSeaError(
                f"OpenSea API error {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except requests.RequestException as exc:
            raise OpenSeaError(f"Request failed: {exc}") from exc

    def get_collection_stats(self, collection_slug: str) -> Dict[str, Any]:
        """Return stats for a collection (floor price, volume, etc.).

        Returns a dict with keys such as:
          - floor_price (ETH)
          - total_volume (ETH)
          - num_owners
          - total_supply
        """
        data = self._get(f"collections/{collection_slug}/stats")
        return data.get("total", data)

    def get_best_listings(
        self,
        collection_slug: str,
        limit: int = 20,
        next_cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return the best (cheapest) active listings for a collection.

        Returns a dict with:
          - listings: list of listing objects
          - next: cursor for pagination
        """
        params: Dict[str, Any] = {"limit": limit}
        if next_cursor:
            params["next"] = next_cursor
        return self._get(f"listings/collection/{collection_slug}/best", params=params)

    def get_nft(self, chain: str, contract_address: str, token_id: str) -> Dict[str, Any]:
        """Return details for a specific NFT."""
        return self._get(f"chain/{chain}/contract/{contract_address}/nfts/{token_id}")

    def get_collection(self, collection_slug: str) -> Dict[str, Any]:
        """Return metadata for a collection."""
        return self._get(f"collections/{collection_slug}")

    def fulfill_listing(
        self,
        listing: Dict[str, Any],
        fulfiller_address: str,
    ) -> Dict[str, Any]:
        """Request fulfillment data for a listing from OpenSea.

        Returns transaction data that can be submitted on-chain.
        """
        payload = {
            "listing": {
                "hash": listing["order_hash"],
                "chain": listing.get("chain", "ethereum"),
                "protocol_address": listing.get("protocol_address"),
            },
            "fulfiller": {"address": fulfiller_address},
        }
        url = f"{OPENSEA_BASE_URL}/listings/fulfillment_data"
        try:
            response = self._session.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            raise OpenSeaError(
                f"Fulfillment error {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except requests.RequestException as exc:
            raise OpenSeaError(f"Fulfillment request failed: {exc}") from exc


def parse_floor_price(stats: Dict[str, Any]) -> Optional[float]:
    """Extract floor price in ETH from collection stats."""
    floor = stats.get("floor_price")
    if floor is None:
        return None
    if isinstance(floor, dict):
        # OpenSea v2 sometimes returns {"unit": "ETH", "value": "0.5"}
        value = floor.get("value")
        if value is not None:
            return float(value)
        return None
    return float(floor)


def parse_listing_price_eth(listing: Dict[str, Any]) -> Optional[float]:
    """Extract price in ETH from a listing object."""
    try:
        current_price = listing.get("current_price")
        if current_price is None:
            # Try nested structure
            price_data = (
                listing.get("price", {}).get("current", {})
            )
            current_price = price_data.get("value")
        if current_price is None:
            return None
        # OpenSea returns price in wei (as string)
        wei = int(current_price)
        return wei / 10**18
    except (TypeError, ValueError, KeyError):
        return None


def filter_listings_by_price(
    listings: List[Dict[str, Any]], max_price_eth: float
) -> List[Dict[str, Any]]:
    """Return listings whose price is at or below max_price_eth."""
    result = []
    for listing in listings:
        price = parse_listing_price_eth(listing)
        if price is not None and price <= max_price_eth:
            result.append(listing)
    return result
