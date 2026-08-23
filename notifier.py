import os
import requests
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def esc(s) -> str:
    """Escape the three characters Telegram's HTML parser cares about."""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))

def send_telegram_status(stats:dict, market_count:int):
    """Send a daily health summary."""
    if not TELEGRAM_CHAT_ID or  not TELEGRAM_TOKEN:
        return

    uptime = datetime.now(timezone.utc) - stats["started_at"]
    days = uptime.days
    hours = uptime.seconds // 3600

    if stats["news_processed"] == 0 or market_count == 0:
        emoji = "🔴"
    elif stats["errors"] > 10:
        emoji = "🟡"
    else:
        emoji = "🟢"

    text = (
        f"{emoji} <b>alphamind daily report</b>\n\n"
        f"Uptime: {days}d {hours}h\n"
        f"Markets tracked: {market_count}\n"
        f"News processed: {stats['news_processed']}\n"
        f"Matched by LLM: {stats['matched']}\n"
        f"Impact analyses: {stats['impact_analyses']}\n"
        f"Alerts: {stats['alerts']}\n\n"
        f"Errors: {stats['errors']}\n"
        f"Last error: {esc(stats['last_error'] or 'none')}"
    )

    try:
        response = requests.post( f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={
                        "chat_id": TELEGRAM_CHAT_ID,
                        "text": text,
                        "parse_mode": "HTML",
                    },
                    timeout=10,)
        if response.status_code != 200:
            print(f"Telegram rejected message: {response.status_code} {response.text}")
    except Exception as e:
        print(f"Telegram heartbeat failed: {e}")


def send_telegram_alert(alert: dict):
    """Send an alert to Telegram. Fails silently if not configured or on error."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    emoji = "🟢" if alert["direction"] == "buy_yes" else "🔴"
    arrow = "▲" if alert["direction"] == "buy_yes" else "▼"

    warning = ""
    if alert["market_liquidity"] < 5000 or alert["market_volume_24h"] < 1000:
        warning = "\n⚠ Thin market — price may be stale, your order could move it.\n"

    text = (
        f"{emoji} <b>ALERT</b>\n\n"
        f"<b>{esc(alert['market_question'])}</b>\n\n"
        f"Market says   ${alert['market_yes_price']:.2f} ({alert['market_yes_price']:.0%})  "
        f"bid ${alert['market_yes_bid']:.2f} / ask ${alert['market_yes_ask']:.2f}\n"
        f"LLM says      ${alert['llm_probability']:.2f} ({alert['llm_probability']:.0%})\n"
        f"Delta         {alert['delta']:+.2f}   weighted {alert['weighted_delta']:+.2f}\n\n"
        f"{arrow} <b>{alert['direction'].replace('_', ' ').upper()}</b>\n\n"
        f"confidence {alert['llm_confidence']:.2f}   not-yet-priced-in {alert['pricing_delay']:.2f}\n"
        f"24h volume ${alert['market_volume_24h']:,.0f}   liquidity ${alert['market_liquidity']:,.0f}\n"
        f"{warning}\n"
        f"─────\n\n"
        f"Triggered by <i>{esc(alert['news_source'])}</i>\n"
        f"{esc(alert['news_title'])}\n\n"
        f"{esc(alert['reasoning'])}\n\n"
        f"{esc(alert['news_url'])}"
    )

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
            },
            timeout=10,
        )
        if response.status_code != 200:
            print(f"Telegram rejected message: {response.status_code} {response.text}")

    except Exception as e:
        print(f"Telegram send failed: {e}")


if __name__ == "__main__":
    fake_alert = {
        "market_question": "Will oil hit $100 by November?",
        "market_yes_price": 0.14,
        "market_yes_bid": 0.13,
        "market_yes_ask": 0.15,
        "market_volume_24h": 25000.0,
        "market_liquidity": 5000.0,
        "llm_probability": 0.35,
        "llm_confidence": 0.70,
        "pricing_delay": 0.80,
        "delta": 0.21,
        "weighted_delta": 0.12,
        "direction": "buy_yes",
        "news_source": "BBC World",
        "news_title": "Iran threatens to close Strait of Hormuz",
        "reasoning": "The Strait carries roughly 20% of global oil supply, and a closure would trigger immediate supply disruption. The market has not fully priced this in.",
        "news_url": "https://polymarket.com/event/oil-100",
    }
    send_telegram_alert(fake_alert)
    print("Sent test alert to Telegram")