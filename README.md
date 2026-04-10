# AH Collector – Auction House Tracker

A full-stack web application for tracking and monitoring NFT / auction-house items, including price history, watchlists, and category filters.

## Tech Stack

| Layer    | Technology                          |
|----------|-------------------------------------|
| Backend  | Python 3.11 · Flask · SQLAlchemy    |
| Database | SQLite (local) / configurable via `DATABASE_URL` env var |
| Frontend | Vanilla HTML · CSS · JavaScript     |
| Hosting  | Google App Engine (Standard)        |

## Features

- **Track items** – Add auction-house items with name, collection, category, and current price.
- **Price history** – Every price update is recorded so you can see how a price has changed over time.
- **Watchlist** – Star items you want to keep a close eye on.
- **Price alerts** – Set min/max thresholds; items outside the range are highlighted on the dashboard.
- **Search & filter** – Filter by keyword or category in real time.
- **REST API** – Clean JSON API consumed by the frontend (and usable by bots/scripts).
- **D33J Testnet** – Proof-of-work blockchain for D33J coin on the deejaeleetta network.

## Quick Start (local development)

```bash
# 1. Create a virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the development server
python main.py
```

Open http://localhost:8080 in your browser.

## API Reference

### Auction House Items

| Method | Endpoint                           | Description                        |
|--------|------------------------------------|------------------------------------|
| GET    | `/api/items`                       | List items (supports `search`, `category`, `watchlisted` query params) |
| GET    | `/api/items/<id>`                  | Get item + price history            |
| POST   | `/api/items`                       | Create item                         |
| PUT    | `/api/items/<id>`                  | Update item                         |
| DELETE | `/api/items/<id>`                  | Delete item                         |
| POST   | `/api/items/<id>/watchlist`        | Toggle watchlist status             |
| GET    | `/api/stats`                       | Dashboard statistics                |

### D33J Testnet Blockchain

| Method | Endpoint                                  | Description                                          |
|--------|-------------------------------------------|------------------------------------------------------|
| GET    | `/api/blockchain/info`                    | Network metadata, chain length, validity             |
| GET    | `/api/blockchain/chain`                   | Full block list (newest first)                       |
| GET    | `/api/blockchain/pending`                 | Unconfirmed transactions in the mempool              |
| GET    | `/api/blockchain/balance/<address>`       | D33J balance for an address                          |
| POST   | `/api/blockchain/transactions/new`        | Queue a transfer (`sender`, `recipient`, `amount`)   |
| POST   | `/api/blockchain/faucet`                  | Request 100 D33J test coins (`address`)              |
| POST   | `/api/blockchain/mine`                    | Mine pending transactions (`miner_address`)          |

## D33J Testnet

The testnet is accessible at `/blockchain`.  Key details:

| Property        | Value                                  |
|-----------------|----------------------------------------|
| Network         | deejaeleetta                           |
| Type            | testnet                                |
| Coin symbol     | D33J                                   |
| Proof-of-work   | SHA-256, difficulty 3                  |
| Mining reward   | 50 D33J / block                        |
| Faucet drip     | 100 D33J / request                     |
| Initial supply  | 1,000,000 D33J (held by testnet faucet)|

Mined blocks are persisted to the SQLite database so the chain survives server restarts.

## Deploying to Google App Engine

```bash
gcloud app deploy
```

## Project Structure

```
ah-collector/
├── main.py              # Flask application & API
├── blockchain.py        # D33J coin blockchain core logic
├── app.yaml             # App Engine configuration
├── requirements.txt     # Python dependencies
├── templates/
│   ├── index.html       # Main dashboard template
│   └── blockchain.html  # D33J testnet dashboard
└── static/
    ├── css/style.css    # Stylesheet
    └── js/app.js        # Frontend JavaScript
```
