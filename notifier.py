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


TELEGRAM_MAX_LENGTH = 4096

def _format_report_alert(e: dict) -> str:
    """One alert's block in the end-of-day report."""
    alert = e["alert"]
    status = e["status"]
    icon = {"hit": "✅", "miss": "❌", "flat": "➖", "too_early": "⏳", "no_data": "❔"}[e["result"]]
    direction = alert["direction"].replace("_", " ").upper()

    if e["price"] is None:
        price_line = f"At alert {alert['market_yes_price']:.2f} → no price data yet"
    elif status is not None and status["resolved"]:
        price_line = (f"At alert {alert['market_yes_price']:.2f} → resolved <b>{esc(status['outcome'])}</b> "
                      f"({e['price']:.2f}, {e['move']:+.2f})")
    else:
        price_line = f"At alert {alert['market_yes_price']:.2f} → now {e['price']:.2f} ({e['move']:+.2f})"

    lines = [
        f"{icon} <b>{esc(alert['market_question'])}</b>",
        f"{direction} · LLM {alert['llm_probability']:.2f} · {e['age_hours']:.1f}h ago",
        price_line,
    ]
    if e["result"] == "too_early":
        lines.append("<i>too early to judge</i>")
    if status is not None and status["closed"] and not status["resolved"]:
        lines.append("<i>market closed, awaiting resolution</i>")
    return "\n".join(lines)

def build_alert_report(evaluations: list[dict]) -> list[str]:
    """Format the end-of-day report as one or more messages, split between alerts."""
    scored = [e for e in evaluations if e["result"] in ("hit", "miss", "flat")]
    hits = sum(1 for e in scored if e["result"] == "hit")
    too_early = sum(1 for e in evaluations if e["result"] == "too_early")

    header = (
        f"📊 <b>Alert report, last 24h</b>\n\n"
        f"<b>{hits} of {len(scored)}</b> alerts moved toward the LLM estimate"
    )
    if too_early:
        header += f"\n{too_early} too early to judge"

    # pack whole alert blocks into messages, leaving room for a "(1/2)" footer
    limit = TELEGRAM_MAX_LENGTH - 20
    messages = []
    current = header
    for block in [_format_report_alert(e) for e in evaluations]:
        if len(current) + 2 + len(block) > limit:
            messages.append(current)
            current = block
        else:
            current += "\n\n" + block
    messages.append(current)

    if len(messages) > 1:
        messages = [f"{m}\n\n({i}/{len(messages)})" for i, m in enumerate(messages, 1)]
    return messages

def send_telegram_report(messages: list[str]) -> bool:
    """Send the end-of-day report messages in order. Returns False if any failed."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return True

    ok = True
    for text in messages:
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
                ok = False

        except Exception as e:
            print(f"Telegram report failed: {e}")
            ok = False
    return ok


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