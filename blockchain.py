"""
D33J Coin Blockchain – Testnet Implementation
Network : deejaeleetta-testnet
Symbol  : D33J
"""

import hashlib
import json
import time
from typing import Dict, List, Optional

# ──────────────────────────────────────────────────────────────────────────────
# Network constants
# ──────────────────────────────────────────────────────────────────────────────

NETWORK_NAME = "deejaeleetta"
NETWORK_TYPE = "testnet"
COIN_SYMBOL = "D33J"
COIN_NAME = "D33J Coin"

MINING_DIFFICULTY = 3          # leading zeros required (testnet-friendly)
MINING_REWARD = 50.0           # D33J per mined block
INITIAL_SUPPLY = 1_000_000.0   # genesis allocation to faucet

GENESIS_ZERO_HASH = "0" * 64
COINBASE_ADDRESS = "0x0000000000000000000000000000000000000000"
FAUCET_ADDRESS = "0xDEEJAE_FAUCET_deejaeleetta_testnet"
FAUCET_DRIP = 100.0            # D33J per faucet request


# ──────────────────────────────────────────────────────────────────────────────
# Block
# ──────────────────────────────────────────────────────────────────────────────

class Block:
    """A single block in the D33J blockchain."""

    def __init__(
        self,
        index: int,
        timestamp: float,
        transactions: List[Dict],
        previous_hash: str,
        nonce: int = 0,
    ) -> None:
        self.index = index
        self.timestamp = timestamp
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = self.calculate_hash()

    # ------------------------------------------------------------------
    def calculate_hash(self) -> str:
        """Return the SHA-256 hash of this block's contents."""
        payload = {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        }
        raw = json.dumps(payload, sort_keys=True).encode()
        return hashlib.sha256(raw).hexdigest()

    # ------------------------------------------------------------------
    def to_dict(self) -> Dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, data: Dict) -> "Block":
        """Reconstruct a Block from its dictionary representation."""
        block = cls(
            index=data["index"],
            timestamp=data["timestamp"],
            transactions=data["transactions"],
            previous_hash=data["previous_hash"],
            nonce=data["nonce"],
        )
        block.hash = data["hash"]
        return block


# ──────────────────────────────────────────────────────────────────────────────
# Blockchain
# ──────────────────────────────────────────────────────────────────────────────

class D33JBlockchain:
    """
    D33J Coin testnet blockchain on the deejaeleetta network.

    Supports:
      - Proof-of-work mining
      - Transaction pool
      - Faucet (testnet token distribution)
      - Balance queries
      - Chain validation
    """

    def __init__(self) -> None:
        self.chain: List[Block] = []
        self.pending_transactions: List[Dict] = []
        self.network = NETWORK_NAME
        self.network_type = NETWORK_TYPE
        self.coin_symbol = COIN_SYMBOL
        self.difficulty = MINING_DIFFICULTY
        self.mining_reward = MINING_REWARD
        self._pow_target = "0" * self.difficulty

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def bootstrap(self, persisted_blocks: Optional[List[Dict]] = None) -> None:
        """
        Initialise the chain.
        If *persisted_blocks* is given (loaded from the DB) the genesis block
        is NOT re-created; otherwise a fresh genesis block is minted.
        """
        if persisted_blocks:
            self.chain = [Block.from_dict(b) for b in persisted_blocks]
        else:
            self._create_genesis_block()

    def _create_genesis_block(self) -> None:
        """Mine the genesis block and fund the testnet faucet."""
        genesis_tx = {
            "sender": COINBASE_ADDRESS,
            "recipient": FAUCET_ADDRESS,
            "amount": INITIAL_SUPPLY,
            "timestamp": 0.0,
            "type": "genesis",
        }
        genesis = Block(
            index=0,
            timestamp=0.0,
            transactions=[genesis_tx],
            previous_hash=GENESIS_ZERO_HASH,
            nonce=0,
        )
        self.chain.append(genesis)

    # ------------------------------------------------------------------
    # Core chain properties
    # ------------------------------------------------------------------

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    def add_transaction(
        self,
        sender: str,
        recipient: str,
        amount: float,
        tx_type: str = "transfer",
    ) -> int:
        """
        Queue a transaction in the pending pool.
        Returns the index of the block that will contain it.
        Raises ValueError on invalid inputs.
        """
        amount = float(amount)
        if amount <= 0:
            raise ValueError("Amount must be positive.")
        if not sender or not recipient:
            raise ValueError("sender and recipient are required.")

        # Balance check (skip for coinbase / faucet)
        if sender not in (COINBASE_ADDRESS, FAUCET_ADDRESS, "coinbase"):
            if self.get_balance(sender) < amount:
                raise ValueError(
                    f"Insufficient balance. "
                    f"Available: {self.get_balance(sender):.4f} {COIN_SYMBOL}"
                )

        self.pending_transactions.append(
            {
                "sender": sender,
                "recipient": recipient,
                "amount": amount,
                "timestamp": time.time(),
                "type": tx_type,
            }
        )
        return self.last_block.index + 1

    def request_faucet(self, address: str) -> int:
        """Send FAUCET_DRIP D33J to *address* from the faucet."""
        if not address:
            raise ValueError("address is required.")
        faucet_balance = self.get_balance(FAUCET_ADDRESS)
        if faucet_balance < FAUCET_DRIP:
            raise ValueError("Faucet is empty.")
        return self.add_transaction(
            sender=FAUCET_ADDRESS,
            recipient=address,
            amount=FAUCET_DRIP,
            tx_type="faucet",
        )

    # ------------------------------------------------------------------
    # Mining
    # ------------------------------------------------------------------

    def _proof_of_work(self, block: Block) -> int:
        """Increment nonce until the block hash meets the difficulty target."""
        nonce = 0
        while True:
            block.nonce = nonce
            candidate = block.calculate_hash()
            if candidate.startswith(self._pow_target):
                return nonce
            nonce += 1

    def mine_pending_transactions(self, miner_address: str) -> Block:
        """
        Bundle pending transactions into a new block and mine it.
        Awards *miner_address* a mining reward.
        Returns the newly mined Block.
        """
        if not miner_address:
            raise ValueError("miner_address is required.")

        reward_tx = {
            "sender": "coinbase",
            "recipient": miner_address,
            "amount": self.mining_reward,
            "timestamp": time.time(),
            "type": "mining_reward",
        }
        txs = list(self.pending_transactions) + [reward_tx]

        new_block = Block(
            index=len(self.chain),
            timestamp=time.time(),
            transactions=txs,
            previous_hash=self.last_block.hash,
        )
        self._proof_of_work(new_block)
        new_block.hash = new_block.calculate_hash()

        self.chain.append(new_block)
        self.pending_transactions = []
        return new_block

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_balance(self, address: str) -> float:
        """Return the confirmed + pending balance of *address*."""
        balance = 0.0
        for block in self.chain:
            for tx in block.transactions:
                if tx["recipient"] == address:
                    balance += tx["amount"]
                if tx["sender"] == address:
                    balance -= tx["amount"]
        for tx in self.pending_transactions:
            if tx["recipient"] == address:
                balance += tx["amount"]
            if tx["sender"] == address:
                balance -= tx["amount"]
        return balance

    def is_chain_valid(self) -> bool:
        """Verify hashes and chain linkage (genesis block excluded from PoW check)."""
        for i in range(1, len(self.chain)):
            curr = self.chain[i]
            prev = self.chain[i - 1]
            if curr.hash != curr.calculate_hash():
                return False
            if curr.previous_hash != prev.hash:
                return False
            if not curr.hash.startswith(self._pow_target):
                return False
        return True

    def get_info(self) -> Dict:
        """Return a metadata summary of the chain."""
        return {
            "network": self.network,
            "network_type": self.network_type,
            "coin_name": COIN_NAME,
            "coin_symbol": self.coin_symbol,
            "chain_length": len(self.chain),
            "difficulty": self.difficulty,
            "mining_reward": self.mining_reward,
            "pending_transactions": len(self.pending_transactions),
            "is_valid": self.is_chain_valid(),
            "faucet_address": FAUCET_ADDRESS,
            "faucet_drip": FAUCET_DRIP,
            "faucet_balance": self.get_balance(FAUCET_ADDRESS),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Module-level singleton (lazy)
# ──────────────────────────────────────────────────────────────────────────────

_chain: Optional[D33JBlockchain] = None


def get_blockchain() -> D33JBlockchain:
    """Return (or create) the process-level blockchain singleton."""
    global _chain
    if _chain is None:
        _chain = D33JBlockchain()
    return _chain
