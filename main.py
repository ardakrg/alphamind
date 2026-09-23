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
)
from fetchers.polymarket import fetch_polymarket_markets, fetch_market_by_id
from fetchers.news import fetch_all_news
from matcher.embedder import embed_texts
from matcher.candidates import find_candidates
from matcher.llm_matcher import verify_matches
from analyzer.impact import analyze_impact
from alerts import evaluate_alert, display_alert
from storage import init_db, store_alert, store_market_prices, get_watchlist_market_ids
from notifier import send_telegram_alert, send_telegram_status

market_list = []
market_embeddings = None
seen_news_ids = set()

stats = {
    "started_at": datetime.now(timezone.utc),
    "news_processed": 0,
    "matched": 0,
    "impact_analyses": 0,
    "alerts": 0,
    "last_error": None,
    "errors": 0,
}

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

    stats["news_processed"] += 1
    
    # Ask the LLM which candidate markets are actually affected by this news.
    relevant = verify_matches(news, candidates)
    if not relevant:
        print("   → no relevant markets")
        return

    stats["matched"] += len(relevant)
    
    # impact analysis for every market using LLM
    for market in relevant:
        impact = analyze_impact(news, market)
        if impact is None:
            continue
        stats["impact_analyses"] += 1

        print(f"    [impact] {market['question'][:45]}")
        print(f"            p={impact['new_probability']:.2f}  conf={impact['confidence']:.2f}  "
            f"delay={impact['market_pricing_delay']:.2f}  "
            f"delta={impact['new_probability'] - market['yes_probability']:+.2f}")

        alert = evaluate_alert(news, market, impact)
        if alert:
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
                cutoff = datetime.now(timezone.utc) - timedelta(INITIAL_LOOKBACK_HOURS)
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

async def daily_report():
    """Send a dialy heartbeat to Telegram"""
    while True:
        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=11, minute=6, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        await asyncio.sleep((next_run - now).total_seconds())
        
        try:
            send_telegram_status(stats, len(market_list))
        except Exception as e:
            stats["errors"] += 1
            print(f"Heartbeat failed: {e}")
        # reset the 24h counters
        stats["news_processed"] = 0
        stats["matched"] = 0
        stats["impact_analyses"] = 0
        stats["alerts"] = 0
        stats["last_error"] = f"{datetime.now(timezone.utc).strftime('%H:%M')} {e}"
        stats["errors"] = 0

async def main():
    init_db()
    print("Starting alphamind...")
    await asyncio.gather(market_updater(), news_watcher(), daily_report(),)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
