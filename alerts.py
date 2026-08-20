from config import MIN_DELTA, MIN_PRICING_DELAY
from datetime import datetime, timezone
from rich.console import Console
from rich.panel import Panel

console = Console()

def evaluate_alert(news:dict, market:dict, impact: dict) -> dict | None:
    """Decide whether this news-market pair warrants an alert."""
    if not impact["affects_market"]:
        return None
    
    delta = impact["new_probability"] - market["yes_probability"]

    if impact["market_pricing_delay"] < MIN_PRICING_DELAY:
        return None

    weighted_delta = delta * impact["confidence"]
    if abs(weighted_delta) < MIN_DELTA:
        return None
    
    direction = None
    if delta > 0:
        direction = "buy_yes"
    else:
        direction = "buy_no"
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "news_source": news["source"],
        "news_title": news["title"],
        "news_url": news["url"],
        "market_id": market["id"],
        "market_question": market["question"],
        "market_yes_price": market["yes_probability"],
        "market_yes_bid": market["yes_bid"],
        "market_yes_ask": market["yes_ask"],
        "market_volume_24h": market["volume_24h"],
        "market_liquidity": market["liquidity"],
        "llm_probability": impact["new_probability"],
        "llm_confidence": impact["confidence"],
        "pricing_delay": impact["market_pricing_delay"],
        "delta": delta,
        "weighted_delta": weighted_delta,
        "direction": direction,
        "reasoning": impact["reasoning"],
    }

def display_alert(alert: dict):
    """Print an alert to the terminal in a readable format."""
    color = "green" if alert["direction"] == "buy_yes" else "red"
    arrow = "▲" if alert["direction"] == "buy_yes" else "▼"
    local_time = datetime.fromisoformat(alert["timestamp"]).astimezone()


    warning = ""
    if alert["market_liquidity"] < 5000 or alert["market_volume_24h"] < 1000:
        warning = (
            "\n[yellow]⚠ Thin market — the price may be stale, and your own order "
            "could move it. Check the book before acting.[/yellow]\n"
        )

    body = f"""[bold]{alert['market_question']}[/bold]

  Market says   [bold]${alert['market_yes_price']:.2f}[/bold] [dim]({alert['market_yes_price']:.0%})[/dim]  [dim]bid ${alert['market_yes_bid']:.2f} / ask ${alert['market_yes_ask']:.2f}[/dim]
  LLM says      [bold {color}]${alert['llm_probability']:.2f}[/bold {color}] [dim]({alert['llm_probability']:.0%})[/dim]
  Delta         [{color}]{alert['delta']:+.2f}[/{color}]   weighted [{color}]{alert['weighted_delta']:+.2f}[/{color}]

  [bold {color}]{arrow} {alert['direction'].replace('_', ' ').upper()}[/bold {color}]

  [dim]confidence[/dim] {alert['llm_confidence']:.2f}   [dim]not-yet-priced-in[/dim] {alert['pricing_delay']:.2f}
  [dim]24h volume[/dim] ${alert['market_volume_24h']:,.0f}   [dim]liquidity[/dim] ${alert['market_liquidity']:,.0f}
{warning}
[dim]─────[/dim]

[dim]Triggered by[/dim] [italic]{alert['news_source']}[/italic]
{alert['news_title']}

{alert['reasoning']}

[dim]{alert['news_url']}[/dim]"""

    console.print(Panel(
        body,
        title=f"[bold {color}]ALERT[/bold {color}]",
        subtitle=f"[dim]{local_time.strftime('%Y-%m-%d %H:%M')}[/dim]",
        border_style=color,
        padding=(1, 2),
    ))


if __name__ == "__main__":
    fake_alert = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "news_source": "BBC World",
        "news_title": "Iran threatens to close Strait of Hormuz",
        "news_url": "https://example.com/test",
        "market_id": "12345",
        "market_question": "Will oil hit $100 by November?",
        "market_yes_price": 0.14,
        "market_yes_bid": 0.13,
        "market_yes_ask": 0.15,
        "market_volume_24h": 25000,
        "market_liquidity": 5000,
        "llm_probability": 0.35,
        "llm_confidence": 0.7,
        "pricing_delay": 0.8,
        "delta": 0.21,
        "weighted_delta": 0.1176,
        "direction": "buy_yes",
        "reasoning": "The Strait of Hormuz carries roughly 20% of global oil supply, and a closure would trigger immediate supply disruption. The market appears not to have fully priced this in yet, given the announcement came within the last hour and volume has not spiked.",    }
    display_alert(fake_alert)