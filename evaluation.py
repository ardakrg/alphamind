import argparse
from datetime import datetime, timezone, timedelta
from config import SNAPSHOT_TOLERANCE_MINUTES
from storage import DB_PATH, get_price_history, get_alerts_since, get_latest_price
from fetchers.polymarket import fetch_market_status
from notifier import build_alert_report, send_telegram_report

HORIZONS = [("+1h", timedelta(hours=1)), ("+6h", timedelta(hours=6)), ("+24h", timedelta(hours=24))]
FLAT_THRESHOLD = 0.005   # moves smaller than this count as no move
TOO_EARLY_HOURS = 1      # younger alerts are shown but not scored
REPORT_WINDOW_HOURS = 24

def nearest_snapshot(history: list[dict], target: datetime, tolerance: timedelta) -> dict | None:
    """Snapshot closest to target, or None if none is within tolerance."""
    best = None
    best_gap = tolerance
    for snap in history:
        gap = abs(datetime.fromisoformat(snap["timestamp"]) - target)
        if gap <= best_gap:
            best = snap
            best_gap = gap
    return best

def score_move(alert: dict, price: float) -> dict:
    """Compare a later price to the price at alert time, in the alert's direction.

    result is "hit" if the price moved toward the LLM estimate (up for buy_yes,
    down for buy_no), "miss" if it moved away, "flat" if it barely moved.
    """
    move = price - alert["market_yes_price"]
    signed_move = move if alert["direction"] == "buy_yes" else -move

    if abs(move) < FLAT_THRESHOLD:
        result = "flat"
    elif signed_move > 0:
        result = "hit"
    else:
        result = "miss"

    return {"price": price, "move": move, "result": result}

def evaluate_alert_moves(alert: dict, now: datetime, db_path: str = DB_PATH) -> dict:
    """Scored price at each horizon, or None for horizons with no data yet."""
    alert_time = datetime.fromisoformat(alert["timestamp"])
    tolerance = timedelta(minutes=SNAPSHOT_TOLERANCE_MINUTES)

    # one query covering all horizons
    history = get_price_history(
        alert["market_id"],
        (alert_time + HORIZONS[0][1] - tolerance).isoformat(),
        (alert_time + HORIZONS[-1][1] + tolerance).isoformat(),
        db_path,
    )

    results = {}
    for label, offset in HORIZONS:
        target = alert_time + offset
        snap = nearest_snapshot(history, target, tolerance) if target <= now else None
        results[label] = score_move(alert, snap["yes_probability"]) if snap else None
    return results

def evaluate_recent_alerts(now: datetime, hours: int = REPORT_WINDOW_HOURS, db_path: str = DB_PATH) -> list[dict]:
    """Where each alert from the last `hours` hours stands right now.

    Each entry has the alert, its age, the market status from the API (None if the
    lookup failed), and price/move/result. result is "hit", "miss" or "flat" when
    scored, "too_early" for young alerts, or "no_data" when there's no price to judge.
    A resolved market is scored on its final price, whatever the alert's age.
    """
    alerts = get_alerts_since((now - timedelta(hours=hours)).isoformat(), db_path)
    statuses = {}
    evaluations = []

    for alert in alerts:
        market_id = alert["market_id"]
        if market_id not in statuses:
            try:
                statuses[market_id] = fetch_market_status(market_id)
            except Exception as e:
                print(f"Status fetch failed for {market_id}: {e}")
                statuses[market_id] = None
        status = statuses[market_id]

        age_hours = (now - datetime.fromisoformat(alert["timestamp"])).total_seconds() / 3600
        resolved = status is not None and status["resolved"] and status["final_yes_price"] is not None

        if resolved:
            price = status["final_yes_price"]
        else:
            latest = get_latest_price(market_id, alert["timestamp"], db_path)
            price = latest["yes_probability"] if latest else None

        if price is None:
            scored = {"price": None, "move": None, "result": "no_data"}
        else:
            scored = score_move(alert, price)
            if age_hours < TOO_EARLY_HOURS and not resolved:
                scored["result"] = "too_early"

        evaluations.append({"alert": alert, "age_hours": age_hours, "status": status, **scored})

    return evaluations

def send_alert_report(now: datetime | None = None, db_path: str = DB_PATH, send: bool = True) -> list[str]:
    """Build the end-of-day report and send it. Sends nothing if there were no alerts.

    Returns the messages, so they can be inspected without sending (send=False).
    """
    now = now or datetime.now(timezone.utc)
    evaluations = evaluate_recent_alerts(now, db_path=db_path)
    if not evaluations:
        return []

    messages = build_alert_report(evaluations)
    if send and not send_telegram_report(messages):
        raise RuntimeError("Telegram did not accept the whole alert report")
    return messages


if __name__ == "__main__":
    # usage: python evaluation.py [--db PATH] [--send]
    parser = argparse.ArgumentParser(description="Build the end-of-day alert report.")
    parser.add_argument("--db", default=DB_PATH, help="database to read (default: %(default)s)")
    parser.add_argument("--send", action="store_true", help="actually send it to Telegram")
    args = parser.parse_args()

    messages = send_alert_report(db_path=args.db, send=args.send)
    if not messages:
        print("No alerts in the last 24 hours, nothing to send.")
    for i, message in enumerate(messages, 1):
        print(f"───── message {i}/{len(messages)} ({len(message)} chars) ─────")
        print(message)
    if messages and not args.send:
        print("\n(dry run, not sent. Add --send to send it to Telegram)")
