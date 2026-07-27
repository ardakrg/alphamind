import requests
from config import MARKET_FETCH_LIMIT
import time

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
        if market.get("active") != True or market.get("closed") != False:
            continue

        yes_bid = market.get("bestBid")
        yes_ask = market.get("bestAsk")
        if yes_bid is None or yes_ask is None:
            continue

        no_bid = round(1 - yes_ask, 4)
        no_ask = round(1- yes_bid, 4)

        yes_probability = (yes_bid + yes_ask) / 2
        url = f"https://polymarket.com/event/{market.get('slug')}"
        volume24h = market.get("volume24hr")
        liquidity = market.get("liquidityNum")
        question = market.get("question")
        market_id = market.get("id")

        result = {
            "id": market_id,
            "question": question,
            "yes_bid": yes_bid,
            "yes_ask": yes_ask,
            "no_bid": no_bid,
            "no_ask": no_ask,
            "yes_probability": yes_probability,
            "volume_24h": volume24h,
            "liquidity": liquidity,
            "url": url,
        }

        results.append(result)
    
    return results


if __name__ == "__main__":
    markets = fetch_polymarket_markets(limit=300)
    for m in markets:
        q = m["question"].lower()
        if "iran" in q or "oil" in q or "hormuz" in q:
            print(f"  {m['question'][:60]}  liq={m['liquidity']:.0f} vol={m['volume_24h']:.0f}")
    print(f"Fetched {len(markets)} markets")
    for m in markets[:5]:
        print(f"  liq={m['liquidity']:.0f} vol={m['volume_24h']:.0f}  {m['question'][:50]}")