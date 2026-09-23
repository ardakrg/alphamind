import requests
from config import MARKET_FETCH_LIMIT
import time

def _standardize(market: dict) -> dict | None:
    """Convert a raw Gamma market into our standard dict. None if closed or no order book."""
    if market.get("active") != True or market.get("closed") != False:
        return None

    yes_bid = market.get("bestBid")
    yes_ask = market.get("bestAsk")
    if yes_bid is None or yes_ask is None:
        return None

    no_bid = round(1 - yes_ask, 4)
    no_ask = round(1- yes_bid, 4)

    yes_probability = (yes_bid + yes_ask) / 2
    url = f"https://polymarket.com/event/{market.get('slug')}"

    return {
        "id": market.get("id"),
        "question": market.get("question"),
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "no_bid": no_bid,
        "no_ask": no_ask,
        "yes_probability": yes_probability,
        "volume_24h": market.get("volume24hr"),
        "liquidity": market.get("liquidityNum"),
        "url": url,
    }

def fetch_polymarket_markets(limit: int = MARKET_FETCH_LIMIT, min_liquidity: float = 1000, order: str = "volume24hr",) -> list[dict]:
    gamma_url = "https://gamma-api.polymarket.com/markets"
    page_size = 100
    raw = []
    offset = 0
    max_retries = 3

    while len(raw) < limit:
        response = requests.get(gamma_url, params={
            "limit": page_size,
            "offset": offset,
            "closed": "false",
            "liquidity_num_min": min_liquidity,
            "order": order,
            "ascending": "false",
        })

        if response.status_code == 429:
            if max_retries <= 0:
                print("Too many rate limits, stopping")
                break
            max_retries -= 1
            print("Rate limited, backing off")
            time.sleep(5)
            continue
        
        page = response.json()
        if not page:
            break
        raw.extend(page)
        offset += page_size
        time.sleep(0.3)   # be polite to the API

    
    results = []

    for market in raw:
        result = _standardize(market)
        if result is not None:
            results.append(result)
    
    return results


def fetch_market_by_id(market_id: str) -> dict | None:
    """Fetch a single market. None if it doesn't exist, is closed, or has no order book."""
    url = f"https://gamma-api.polymarket.com/markets/{market_id}"
    max_retries = 3

    while True:
        response = requests.get(url, timeout=10)

        if response.status_code == 429 and max_retries > 0:
            max_retries -= 1
            print("Rate limited, backing off")
            time.sleep(5)
            continue
        break

    if response.status_code == 404:
        return None
    response.raise_for_status()

    return _standardize(response.json())


if __name__ == "__main__":
    markets = fetch_polymarket_markets(limit=300)
    for m in markets:
        q = m["question"].lower()
        if "iran" in q or "oil" in q or "hormuz" in q:
            print(f"  {m['question'][:60]}  liq={m['liquidity']:.0f} vol={m['volume_24h']:.0f}")
    print(f"Fetched {len(markets)} markets")
    for m in markets[:5]:
        print(f"  liq={m['liquidity']:.0f} vol={m['volume_24h']:.0f}  {m['question'][:50]}")

    # Single market lookups: an open one, a closed one, and one that doesn't exist
    open_id = markets[0]["id"]
    print(f"\nfetch_market_by_id({open_id}): {fetch_market_by_id(open_id)}")
    print(f"fetch_market_by_id(540817) [closed]: {fetch_market_by_id('540817')}")
    print(f"fetch_market_by_id(999999999) [missing]: {fetch_market_by_id('999999999')}")
