# ah-collector — NFT Collector Bot

An automated NFT collector bot that monitors OpenSea collections for floor-price
opportunities and optionally purchases NFTs that meet your configured criteria.
It exposes a lightweight Flask web API so you can control and inspect the bot at
runtime, and it is ready to deploy to **Google App Engine**.

---

## Features

| Feature | Description |
|---|---|
| **Collection monitoring** | Watch any number of OpenSea collections |
| **Floor-price alerts** | Detect when a collection's floor falls below your budget |
| **Automated buying** | Fulfill the cheapest available listing when criteria are met |
| **Trait filtering** | Restrict purchases to NFTs with specific traits |
| **Gas-price guard** | Skip purchases when the Ethereum gas price is too high |
| **Dry-run mode** | Simulate every action without spending real ETH (default) |
| **Portfolio tracking** | Record every acquired NFT and the ETH spent |
| **REST API** | Start/stop/inspect the bot over HTTP |

---

## Quick Start

### 1. Clone and install dependencies

```bash
git clone https://github.com/DeeJae-LeEtta-LLC/ah-collector.git
cd ah-collector
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env and fill in your OPENSEA_API_KEY, WALLET_ADDRESS, etc.
```

> ⚠️ **Security**: Never commit your `.env` file or `WALLET_PRIVATE_KEY` to version control.

### 3. Run the bot

**As a web server** (recommended):

```bash
python main.py
# Listening on http://localhost:8080
```

**As a standalone script** (no web server):

```python
from nft_collector.config import load_config, CollectionConfig
from nft_collector.bot import NFTCollectorBot

config = load_config()
bot = NFTCollectorBot(config)

# Watch Bored Ape Yacht Club — alert only (auto_buy=False)
bot.add_collection(CollectionConfig(
    slug="boredapeyachtclub",
    name="BAYC",
    max_price_eth=5.0,
    auto_buy=False,
))

bot.run()  # blocks — Ctrl-C to stop
```

---

## REST API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/status` | Bot status and portfolio summary |
| `GET` | `/collections` | List watched collections |
| `POST` | `/collections` | Add a collection to watch |
| `GET` | `/portfolio` | Portfolio summary |
| `POST` | `/tick` | Trigger one monitoring cycle |
| `POST` | `/start` | Start background monitoring loop |
| `POST` | `/stop` | Stop background monitoring loop |

### Add a collection (example)

```bash
curl -X POST http://localhost:8080/collections \
  -H "Content-Type: application/json" \
  -d '{"slug":"boredapeyachtclub","name":"BAYC","max_price_eth":5.0,"auto_buy":false}'
```

### Trigger a manual check

```bash
curl -X POST http://localhost:8080/tick
```

---

## Configuration Reference

All configuration is read from environment variables (see `.env.example`).

| Variable | Default | Description |
|---|---|---|
| `OPENSEA_API_KEY` | — | **Required.** Your OpenSea API key |
| `WALLET_ADDRESS` | — | **Required.** Ethereum wallet address |
| `WALLET_PRIVATE_KEY` | — | Required for real purchases; read at runtime from env |
| `ETH_RPC_URL` | `https://eth.llamarpc.com` | Ethereum JSON-RPC endpoint |
| `DRY_RUN` | `true` | Set to `false` to enable real purchases |
| `CHECK_INTERVAL_SECONDS` | `60` | Seconds between collection checks |
| `MAX_GAS_GWEI` | `50.0` | Skip purchases when gas exceeds this |
| `NETWORK` | `ethereum` | Blockchain network name |

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Deploying to Google App Engine

1. Fill in `app.yaml` with your environment variables (or use App Engine's secret manager).
2. Deploy:

```bash
gcloud app deploy
```

---

## Project Structure

```
ah-collector/
├── app.yaml              # Google App Engine configuration
├── main.py               # Flask web API entry point
├── requirements.txt      # Python dependencies
├── .env.example          # Example environment variables
├── nft_collector/
│   ├── bot.py            # Main bot orchestration loop
│   ├── collector.py      # NFT portfolio tracker
│   ├── config.py         # Configuration management
│   ├── marketplace.py    # OpenSea API v2 client
│   └── wallet.py         # Web3 wallet integration
└── tests/
    ├── conftest.py        # Shared pytest fixtures
    ├── test_bot.py        # Bot tests
    ├── test_collector.py  # Collector tests
    └── test_marketplace.py# Marketplace tests
```

---

## License

MIT © 2024 DeeJae LeEtta LLC
