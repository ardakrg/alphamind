import feedparser

FEEDS = {
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "NYT World": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "NPR": "https://feeds.npr.org/1001/rss.xml",
    "CNBC Top": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "CNBC Economy": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
}

def fetch_feed(source_name: str, url: str) -> list[dict]:
    """Fetch and parse a single RSS feed into standardized news items."""
    parsed = feedparser.parse(url)
    news = []

    for entry in parsed.entries:
        news_entry = {
            "id": entry.get("id"),
            "source": source_name,
            "title": entry.get("title"),
            "summary": entry.get("summary"),
            "url": entry.get("link"),
            "published": entry.get("published"),
        }
        news.append(news_entry)
    
    return news

def fetch_all_news(feeds: dict = FEEDS) -> list[dict]:
    """Fetch all configured feeds and combine into one list."""
    news = []
    for source_name, url in feeds.items():
        try:
            news.extend(fetch_feed(source_name, url))
        except Exception as e:
            print(f"Failed to fetch {source_name}: {e}")
    
    # Deduplicate by id (same story may appear in multiple feeds)
    seen = set()
    unique_news = []
    for item in news:
        if item["id"] not in seen:
            seen.add(item["id"])
            unique_news.append(item)

    return unique_news


if __name__ == "__main__":
    news = fetch_all_news()
    print(f"Fetched {len(news)} unique news items")
    for item in news[:5]:   # first 5
        print(f"[{item['source']}] {item['title']}")