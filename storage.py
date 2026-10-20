import sqlite3
from datetime import datetime, timezone, timedelta

DB_PATH= "alphamind.db"

def init_db(db_path: str = DB_PATH):
    """Create the alerts and market_price_history tables if they don't exist."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute("""CREATE TABLE IF NOT EXISTS alerts (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       timestamp TEXT NOT NULL,
                       news_source TEXT,
                       news_title TEXT,
                       news_url TEXT,
                       market_id TEXT,
                       market_question TEXT,
                       market_yes_price REAL,
                       market_yes_bid REAL,
                       market_yes_ask REAL,
                       market_volume_24h REAL,
                       market_liquidity REAL,
                       llm_probability REAL,
                       llm_confidence REAL,
                       pricing_delay REAL,
                       delta REAL,
                       weighted_delta REAL,
                       direction TEXT,
                       reasoning TEXT
                       )
                       """)
        cursor.execute("""CREATE TABLE IF NOT EXISTS market_price_history (
                       id INTEGER PRIMARY KEY,
                       market_id TEXT,
                       timestamp TEXT,
                       yes_bid REAL,
                       yes_ask REAL,
                       yes_probability REAL
                       )
                       """)
        cursor.execute("""CREATE INDEX IF NOT EXISTS idx_price_history_market_time
                       ON market_price_history (market_id, timestamp)
                       """)

def store_alert(alert: dict, db_path: str = DB_PATH):
    """Insert an alert into the alerts table."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO alerts (
            timestamp, news_source, news_title, news_url,
            market_id, market_question, market_yes_price,
            market_yes_bid, market_yes_ask,
            market_volume_24h, market_liquidity,
            llm_probability, llm_confidence, pricing_delay, 
            delta, weighted_delta, direction, reasoning
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            alert["timestamp"],
            alert["news_source"],
            alert["news_title"],
            alert["news_url"],
            alert["market_id"],
            alert["market_question"],
            alert["market_yes_price"],
            alert["market_yes_bid"],
            alert["market_yes_ask"],
            alert["market_volume_24h"],
            alert["market_liquidity"],
            alert["llm_probability"],
            alert["llm_confidence"],
            alert["pricing_delay"],
            alert["delta"],
            alert["weighted_delta"],
            alert["direction"],
            alert["reasoning"]
        )
        )

def store_market_prices(markets: list[dict], db_path: str = DB_PATH):
    """Insert current market prices into the price history table."""
    timestamp = datetime.now(timezone.utc).isoformat()

    rows = [
        (
            market["id"],
            timestamp,
            market["yes_bid"],
            market["yes_ask"],
            market["yes_probability"],
        )
        for market in markets
    ]

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT INTO market_price_history (
                market_id, timestamp, yes_bid, yes_ask, yes_probability
                           ) VALUES (?, ?, ?, ?, ?)
        """, rows)


def get_recent_alerts(limit: int = 20, db_path: str = DB_PATH) -> list[dict]:
    """Fetch the most recent alerts, newest first."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_watchlist_market_ids(hours: int, db_path: str = DB_PATH) -> list[str]:
    """Market ids that had an alert in the last `hours` hours."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT market_id FROM alerts WHERE timestamp >= ?",
            (cutoff,)
        )
        return [row[0] for row in cursor.fetchall()]

def get_price_history(market_id: str, start: str, end: str, db_path: str = DB_PATH) -> list[dict]:
    """Price snapshots for one market between two ISO timestamps, oldest first."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """SELECT timestamp, yes_bid, yes_ask, yes_probability
               FROM market_price_history
               WHERE market_id = ? AND timestamp BETWEEN ? AND ?
               ORDER BY timestamp""",
            (market_id, start, end)
        )
        return [dict(row) for row in cursor.fetchall()]

def get_alerts_since(since: str, db_path: str = DB_PATH) -> list[dict]:
    """All alerts at or after an ISO timestamp, oldest first."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM alerts WHERE timestamp >= ? ORDER BY timestamp",
            (since,)
        )
        return [dict(row) for row in cursor.fetchall()]

def get_last_alert(market_id: str, since: str, db_path: str = DB_PATH) -> dict | None:
    """Most recent alert for a market at or after an ISO timestamp."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM alerts
               WHERE market_id = ? AND timestamp >= ?
               ORDER BY timestamp DESC LIMIT 1""",
            (market_id, since)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

def get_latest_price(market_id: str, since: str, db_path: str = DB_PATH) -> dict | None:
    """Most recent price snapshot for a market at or after an ISO timestamp."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """SELECT timestamp, yes_bid, yes_ask, yes_probability
               FROM market_price_history
               WHERE market_id = ? AND timestamp >= ?
               ORDER BY timestamp DESC LIMIT 1""",
            (market_id, since)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

if __name__ == "__main__":
    import os

    TEST_DB = "test_alphamind.db"

    # Clean slate
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    init_db(TEST_DB)
    print(f"Test database initialized at {TEST_DB}")

    fake_alert = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "news_source": "BBC World",
        "news_title": "Test: Iran threatens to close Strait of Hormuz",
        "news_url": "https://example.com/test",
        "market_id": "12345",
        "market_question": "Will oil hit $100 by November?",
        "market_yes_price": 0.14,
        "market_yes_bid": 0.13,
        "market_yes_ask": 0.15,
        "market_volume_24h": 25000.0,
        "market_liquidity": 5000.0,
        "llm_probability": 0.35,
        "llm_confidence": 0.7,
        "pricing_delay": 0.8,
        "delta": 0.21,
        "weighted_delta": 0.1176,
        "direction": "buy_yes",
        "reasoning": "Test reasoning.",
    }
    store_alert(fake_alert, TEST_DB)
    print("Stored a test alert")

    fake_markets = [
        {"id": "12345", "yes_bid": 0.13, "yes_ask": 0.15, "yes_probability": 0.14},
        {"id": "67890", "yes_bid": 0.50, "yes_ask": 0.52, "yes_probability": 0.51},
    ]
    store_market_prices(fake_markets, TEST_DB)
    print(f"Stored {len(fake_markets)} market price snapshots")

    alerts = get_recent_alerts(limit=5, db_path=TEST_DB)
    print(f"\nRead back {len(alerts)} alerts:")
    for a in alerts:
        print(f"  [{a['timestamp']}] {a['news_title']}")
        print(f"     market: {a['market_yes_price']}, llm: {a['llm_probability']}, delta: {a['delta']}")

    watchlist = get_watchlist_market_ids(hours=48, db_path=TEST_DB)
    print(f"\nWatchlist (last 48h): {watchlist}")

    now = datetime.now(timezone.utc)
    history = get_price_history(
        "12345",
        (now - timedelta(hours=1)).isoformat(),
        (now + timedelta(hours=1)).isoformat(),
        TEST_DB,
    )
    print(f"Price history for 12345: {history}")

    since = (now - timedelta(hours=24)).isoformat()
    print(f"Alerts in last 24h: {len(get_alerts_since(since, TEST_DB))}")
    print(f"Latest price for 12345: {get_latest_price('12345', since, TEST_DB)}")

    # Cleanup
    os.remove(TEST_DB)
    print(f"\nRemoved {TEST_DB}")

    # Initialize the real DB (empty, ready for use)
    init_db()
    print(f"Real database initialized at {DB_PATH}")