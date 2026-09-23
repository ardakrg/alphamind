import sys
from datetime import datetime, timezone, timedelta
from rich.console import Console
from rich.table import Table
from config import SNAPSHOT_TOLERANCE_MINUTES
from storage import get_recent_alerts, get_price_history

HORIZONS = [("+1h", timedelta(hours=1)), ("+6h", timedelta(hours=6)), ("+24h", timedelta(hours=24))]
FLAT_THRESHOLD = 0.005   # moves smaller than this count as no move

console = Console()

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

def evaluate_alert_moves(alert: dict, now: datetime) -> dict:
    """Price at each horizon and whether it moved in the alert's direction.

    Returns {label: None} for horizons with no data yet, otherwise
    {label: {"price": p, "move": p - alert_price, "result": "hit" | "miss" | "flat"}}.
    """
    alert_time = datetime.fromisoformat(alert["timestamp"])
    tolerance = timedelta(minutes=SNAPSHOT_TOLERANCE_MINUTES)

    # one query covering all horizons
    history = get_price_history(
        alert["market_id"],
        (alert_time + HORIZONS[0][1] - tolerance).isoformat(),
        (alert_time + HORIZONS[-1][1] + tolerance).isoformat(),
    )

    results = {}
    for label, offset in HORIZONS:
        target = alert_time + offset
        snap = nearest_snapshot(history, target, tolerance) if target <= now else None
        if snap is None:
            results[label] = None
            continue

        price = snap["yes_probability"]
        move = price - alert["market_yes_price"]
        signed_move = move if alert["direction"] == "buy_yes" else -move

        if abs(move) < FLAT_THRESHOLD:
            result = "flat"
        elif signed_move > 0:
            result = "hit"
        else:
            result = "miss"

        results[label] = {"price": price, "move": move, "result": result}
    return results

def format_cell(outcome: dict | None) -> str:
    if outcome is None:
        return "[dim]n/a[/dim]"
    mark = {"hit": "[green]✓[/green]", "miss": "[red]✗[/red]", "flat": "[dim]=[/dim]"}[outcome["result"]]
    return f"{outcome['price']:.2f} [dim]({outcome['move']:+.2f})[/dim] {mark}"

def print_report(limit: int = 100):
    alerts = get_recent_alerts(limit=limit)
    if not alerts:
        console.print("No alerts yet.")
        return

    now = datetime.now(timezone.utc)
    table = Table(title=f"Alert evaluation ({len(alerts)} most recent)")
    table.add_column("Time")
    table.add_column("Market", max_width=45)
    table.add_column("Dir")
    table.add_column("At alert", justify="right")
    table.add_column("LLM", justify="right")
    for label, _ in HORIZONS:
        table.add_column(label, justify="right")

    counts = {label: {"hit": 0, "miss": 0, "flat": 0} for label, _ in HORIZONS}

    for alert in alerts:
        outcomes = evaluate_alert_moves(alert, now)
        for label, outcome in outcomes.items():
            if outcome is not None:
                counts[label][outcome["result"]] += 1

        color = "green" if alert["direction"] == "buy_yes" else "red"
        local_time = datetime.fromisoformat(alert["timestamp"]).astimezone()
        table.add_row(
            local_time.strftime("%m-%d %H:%M"),
            alert["market_question"],
            f"[{color}]{alert['direction'].replace('_', ' ')}[/{color}]",
            f"{alert['market_yes_price']:.2f}",
            f"[{color}]{alert['llm_probability']:.2f}[/{color}]",
            *[format_cell(outcomes[label]) for label, _ in HORIZONS],
        )

    console.print(table)

    for label, c in counts.items():
        decided = c["hit"] + c["miss"]
        rate = f"{c['hit'] / decided:.0%}" if decided else "n/a"
        console.print(f"  {label:>5}  [green]✓ {c['hit']}[/green]  [red]✗ {c['miss']}[/red]  "
                      f"[dim]= {c['flat']}[/dim]   moved toward LLM: {rate}")


if __name__ == "__main__":
    # usage: python analyze.py [number_of_alerts]
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    print_report(limit)
