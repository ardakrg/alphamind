import requests

def fetch_polymarket_markets(limit: int = 100, min_volume: float = 10000, min_liquidity: float = 1000) -> list[dict]:
    gamma_url = "https://gamma-api.polymarket.com/markets"
    response = requests.get(gamma_url, params={
        "limit": limit,
        "volume_num_min": min_volume,
        "liquidity_num_min": min_liquidity,
        "closed": "false",
        })
    markets = response.json()
    results = []

    for market in markets:
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
    markets = fetch_polymarket_markets(limit=10)
    print(f"Fetched {len(markets)} markets")
    for m in markets:
        print(m)