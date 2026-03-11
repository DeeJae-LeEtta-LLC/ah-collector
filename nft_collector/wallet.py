"""Web3 wallet integration for the NFT collector bot."""

import logging
import os
from typing import Any, Dict, Optional

from web3 import Web3
from web3.exceptions import ContractLogicError

logger = logging.getLogger(__name__)

WEI_PER_ETH = 10**18


class WalletError(Exception):
    """Raised when a wallet operation fails."""


class Wallet:
    """Manages Ethereum wallet interactions via Web3."""

    def __init__(self, rpc_url: str, address: str, private_key: Optional[str] = None) -> None:
        self._w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self._w3.is_connected():
            raise WalletError(f"Cannot connect to Ethereum node at {rpc_url}")
        self.address = Web3.to_checksum_address(address)
        self._private_key = private_key or os.environ.get("WALLET_PRIVATE_KEY")

    @property
    def is_connected(self) -> bool:
        """Return True if connected to an Ethereum node."""
        return self._w3.is_connected()

    def get_eth_balance(self) -> float:
        """Return the ETH balance of the wallet."""
        try:
            balance_wei = self._w3.eth.get_balance(self.address)
            return balance_wei / WEI_PER_ETH
        except Exception as exc:
            raise WalletError(f"Failed to get ETH balance: {exc}") from exc

    def get_gas_price_gwei(self) -> float:
        """Return the current gas price in Gwei."""
        try:
            gas_price_wei = self._w3.eth.gas_price
            return gas_price_wei / 10**9
        except Exception as exc:
            raise WalletError(f"Failed to get gas price: {exc}") from exc

    def send_transaction(self, tx_data: Dict[str, Any]) -> str:
        """Sign and send a transaction; return the transaction hash."""
        if not self._private_key:
            raise WalletError("Private key not configured — cannot sign transactions")

        try:
            tx = dict(tx_data)
            tx.setdefault("from", self.address)
            tx.setdefault("nonce", self._w3.eth.get_transaction_count(self.address))
            if "gasPrice" not in tx and "maxFeePerGas" not in tx:
                tx["gasPrice"] = self._w3.eth.gas_price

            signed = self._w3.eth.account.sign_transaction(tx, self._private_key)
            tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
            return tx_hash.hex()
        except ContractLogicError as exc:
            raise WalletError(f"Contract reverted: {exc}") from exc
        except Exception as exc:
            raise WalletError(f"Transaction failed: {exc}") from exc

    def wait_for_receipt(self, tx_hash: str, timeout: int = 120) -> Dict[str, Any]:
        """Wait for a transaction receipt and return it."""
        try:
            receipt = self._w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=timeout
            )
            return dict(receipt)
        except Exception as exc:
            raise WalletError(f"Failed waiting for receipt of {tx_hash}: {exc}") from exc

    def has_sufficient_balance(self, required_eth: float, gas_buffer_eth: float = 0.01) -> bool:
        """Return True if the wallet has enough ETH (including a gas buffer)."""
        balance = self.get_eth_balance()
        return balance >= required_eth + gas_buffer_eth
