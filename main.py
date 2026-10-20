import asyncio
from datetime import datetime, timezone, timedelta
from config import (
    MARKET_FETCH_LIMIT,
    MARKET_REFRESH_INTERVAL,
    NEWS_CHECK_INTERVAL,
    TOP_K_CANDIDATES,
    MIN_SIMILARITY,
    INITIAL_LOOKBACK_HOURS,
    WATCHLIST_HOURS,
    ANALYSIS_COOLDOWN_HOURS,
)
from fetchers.polymarket import fetch_polymarket_markets, fetch_market_by_id
from fetchers.news import fetch_all_news
from matcher.embedder import embed_texts
from matcher.candidates import find_candidates
from matcher.llm_matcher import verify_matches
from analyzer.impact import analyze_impact
from alerts import evaluate_alert, suppression_reason, display_alert
from storage import init_db, store_alert, store_market_prices, get_watchlist_market_ids
from notifier import send_telegram_alert, send_telegram_status
from evaluation import send_alert_report
import llm_utils

market_list = []
market_embeddings = None
seen_news_ids = set()
last_analyzed = {}   # market_id -> UTC datetime of its last impact analysis (lost on restart)

stats = {
    "started_at": datetime.now(timezone.utc),
    "news_processed": 0,
    "matched": 0,
    "impact_analyses": 0,
    "search_verifications": 0,
    "alerts": 0,
    "last_error": None,
    "errors": 0,
}

def analysis_cooldown_left(market_id: str, now: datetime) -> timedelta | None:
    """Time until a market may be analyzed again, or None if it isn't cooling down."""
    analyzed_at = last_analyzed.get(market_id)
    if analyzed_at is None:
        return None
    left = analyzed_at + timedelta(hours=ANALYSIS_COOLDOWN_HOURS) - now
    return left if left > timedelta(0) else None

def fetch_watchlist_markets(exclude_ids: set) -> list[dict]:
    """Fetch recently alerted markets that aren't already in the top-volume list."""
    markets = []
    for market_id in get_watchlist_market_ids(WATCHLIST_HOURS):
        if market_id in exclude_ids:
            continue
        try:
            market = fetch_market_by_id(market_id)
        except Exception as e:
            print(f"Watchlist fetch failed for {market_id}: {e}")
            continue
        if market is not None:   # None = closed or gone, nothing to store
            markets.append(market)
    return markets

async def market_updater():
    """Fetches market infos and embededs them into vectors"""
    global market_list, market_embeddings
    while True:
        try:
            markets = fetch_polymarket_markets(limit=MARKET_FETCH_LIMIT)
            watchlist = fetch_watchlist_markets({m["id"] for m in markets})
            store_market_prices(markets + watchlist)
            
            embeddings = embed_texts([m["question"] for m in markets])

            market_list = markets
            market_embeddings = embeddings

            print(f"Loaded {len(markets)} markets (+{len(watchlist)} from watchlist).")
        except Exception as e:
            stats["errors"] += 1
            stats["last_error"] = f"{datetime.now(timezone.utc).strftime('%H:%M')} {e}"
            print(f"Market update failed: {e}")

        await asyncio.sleep(MARKET_REFRESH_INTERVAL)

def print_impact(label: str, market: dict, impact: dict):
    print(f"    [impact:{label}] {market['question'][:45]}")
    print(f"            p={impact['new_probability']:.2f}  conf={impact['confidence']:.2f}  "
          f"delay={impact['market_pricing_delay']:.2f}  "
          f"delta={impact['new_probability'] - market['yes_probability']:+.2f}")

async def process_news(news: dict):
    """Run the full pipeline for a single news item."""
    if market_embeddings is None:
        return
        
    text = news["title"] + " " + (news["summary"] or "")
    news_vec = embed_texts([text])[0]

    # Find the most semantically similar corpus items to a query vector.
    candidates = find_candidates(news_vec, market_embeddings, market_list,
                                 top_k=TOP_K_CANDIDATES, min_similarity=MIN_SIMILARITY)
    if not candidates:
        return

    print(f"\n{'─' * 70}")
    print(f"[{news['source']}] {news['title'][:60]}")

    # Drop markets analyzed recently (same event from another feed). Done on the top-k,
    # not the corpus, so a near-duplicate market can't slide into the freed slot.
    now = datetime.now(timezone.utc)
    fresh = []
    for market, score in candidates:
        left = analysis_cooldown_left(market["id"], now)
        if left is None:
            fresh.append((market, score))
        else:
            print(f"   [analysis-cooldown] market={market['id']} {left.total_seconds() / 3600:.1f}h left | {market['question'][:45]}")
    candidates = fresh
    if not candidates:
        print("   → all candidates in analysis cooldown")
        return

    stats["news_processed"] += 1
    
    # Ask the LLM which candidate markets are actually affected by this news.
    relevant = verify_matches(news, candidates)
    if not relevant:
        print("   → no relevant markets")
        return

    stats["matched"] += len(relevant)
    
    # Two-pass impact analysis: a cheap pass from the news alone, then a web-search pass
    # only for markets where the first pass would produce an alert.
    for market in relevant:
        last_analyzed[market["id"]] = datetime.now(timezone.utc)
        impact = analyze_impact(news, market, with_search=False)
        if impact is None:
            continue
        stats["impact_analyses"] += 1
        print_impact("news-only", market, impact)

        if evaluate_alert(news, market, impact) is None:
            continue

        impact = analyze_impact(news, market, with_search=True)
        if impact is None:
            continue
        stats["search_verifications"] += 1
        print_impact("searched", market, impact)

        alert = evaluate_alert(news, market, impact)
        if alert is None:
            print(f"    [search-dropped] market={market['id']} no longer passes the alert filters after search")
        else:
            reason = suppression_reason(alert)
            if reason:
                print(f"    {reason}")
                continue
            stats["alerts"] += 1
            display_alert(alert)
            send_telegram_alert(alert)
            store_alert(alert)

async def news_watcher():
    """Poll RSS feeds and process news items we haven't seen yet."""
    global seen_news_ids
    first_run = True

    while True:
        try:
            news_items = fetch_all_news()

            if first_run:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=INITIAL_LOOKBACK_HOURS)
                for n in news_items:
                    seen_news_ids.add(n["id"])
                    if n["published_dt"] and n["published_dt"] > cutoff:
                        await process_news(n)
                first_run = False
                print(f"Initial scan done. Watching {len(seen_news_ids)} known items.")
            else:
                for n in news_items:
                    if n["id"] not in seen_news_ids:
                        seen_news_ids.add(n["id"])
                        await process_news(n)

        except Exception as e:
            stats["errors"] += 1
            stats["last_error"] = f"{datetime.now(timezone.utc).strftime('%H:%M')} {e}"
            print(f"News check failed: {e}")


        await asyncio.sleep(NEWS_CHECK_INTERVAL)

async def sleep_until(hour: int, minute: int):
    """Sleep until the next HH:MM UTC."""
    now = datetime.now(timezone.utc)
    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    await asyncio.sleep((next_run - now).total_seconds())

async def daily_report():
    """Send a dialy heartbeat to Telegram"""
    while True:
        await sleep_until(11, 6)

        try:
            send_telegram_status(stats, len(market_list), llm_utils.usage_totals)
        except Exception as e:
            stats["errors"] += 1
            print(f"Heartbeat failed: {e}")
        # reset the 24h counters
        stats["news_processed"] = 0
        stats["matched"] = 0
        stats["impact_analyses"] = 0
        stats["search_verifications"] = 0
        stats["alerts"] = 0
        stats["last_error"] = None
        stats["errors"] = 0
        llm_utils.usage_totals.clear()

async def alert_report():
    """Send the end-of-day report on how today's alerts played out."""
    while True:
        await sleep_until(18, 0)

        try:
            messages = send_alert_report()
            if messages:
                print(f"Alert report sent ({len(messages)} messages).")
            else:
                print("No alerts in the last 24h, alert report skipped.")
        except Exception as e:
            stats["errors"] += 1
            stats["last_error"] = f"{datetime.now(timezone.utc).strftime('%H:%M')} {e}"
            print(f"Alert report failed: {e}")

async def main():
    init_db()
    print("Starting alphamind...")
    await asyncio.gather(market_updater(), news_watcher(), daily_report(), alert_report(),)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
