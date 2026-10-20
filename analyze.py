import argparse
from datetime import datetime, timezone
from rich.console import Console
from rich.table import Table
from storage import DB_PATH, get_recent_alerts, get_alerts_since
from evaluation import HORIZONS, evaluate_alert_moves

console = Console()

def format_cell(outcome: dict | None) -> str:
    if outcome is None:
        return "[dim]n/a[/dim]"
    mark = {"hit": "[green]✓[/green]", "miss": "[red]✗[/red]", "flat": "[dim]=[/dim]"}[outcome["result"]]
    return f"{outcome['price']:.2f} [dim]({outcome['move']:+.2f})[/dim] {mark}"

def rate(hits: int, total: int) -> str:
    return f"{hits / total:.0%}" if total else "n/a"

def print_report(limit: int = 100, since: str | None = None, db_path: str = DB_PATH):
    if since:
        since_iso = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc).isoformat()
        alerts = get_alerts_since(since_iso, db_path)[::-1][:limit]   # newest first
        title = f"Alert evaluation ({len(alerts)} most recent since {since} UTC)"
    else:
        alerts = get_recent_alerts(limit=limit, db_path=db_path)
        title = f"Alert evaluation ({len(alerts)} most recent)"
    if not alerts:
        console.print("No alerts yet.")
        return

    now = datetime.now(timezone.utc)
    table = Table(title=title)
    table.add_column("Time")
    table.add_column("Market", max_width=45)
    table.add_column("Dir")
    table.add_column("At alert", justify="right")
    table.add_column("LLM", justify="right")
    for label, _ in HORIZONS:
        table.add_column(label, justify="right")

    counts = {label: {"hit": 0, "miss": 0, "flat": 0} for label, _ in HORIZONS}

    for alert in alerts:
        outcomes = evaluate_alert_moves(alert, now, db_path)
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
        scored = c["hit"] + c["miss"] + c["flat"]
        moved = c["hit"] + c["miss"]
        console.print(f"  {label:>5}  [green]✓ {c['hit']}[/green]  [red]✗ {c['miss']}[/red]  "
                      f"[dim]= {c['flat']}[/dim]   moved toward LLM: {rate(c['hit'], scored)} of all, "
                      f"{rate(c['hit'], moved)} of the {moved} that moved")


if __name__ == "__main__":
    # usage: python analyze.py [number_of_alerts] [--since YYYY-MM-DD] [--db PATH]
    parser = argparse.ArgumentParser(description="Score past alerts against later price moves.")
    parser.add_argument("limit", nargs="?", type=int, default=100, help="max alerts to show (default: %(default)s)")
    parser.add_argument("--since", help="only alerts on or after this UTC date, YYYY-MM-DD")
    parser.add_argument("--db", default=DB_PATH, help="database to read (default: %(default)s)")
    args = parser.parse_args()

    print_report(args.limit, args.since, args.db)
