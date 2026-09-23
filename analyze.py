import sys
from datetime import datetime, timezone
from rich.console import Console
from rich.table import Table
from storage import get_recent_alerts
from evaluation import HORIZONS, evaluate_alert_moves

console = Console()

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
        scored = c["hit"] + c["miss"] + c["flat"]
        rate = f"{c['hit'] / scored:.0%}" if scored else "n/a"
        console.print(f"  {label:>5}  [green]✓ {c['hit']}[/green]  [red]✗ {c['miss']}[/red]  "
                      f"[dim]= {c['flat']}[/dim]   moved toward LLM: {rate}")


if __name__ == "__main__":
    # usage: python analyze.py [number_of_alerts]
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    print_report(limit)
