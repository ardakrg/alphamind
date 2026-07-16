from llm_utils import get_client, parse_llm_json
from config import MATCHER_MODEL
from datetime import datetime


def build_prompt(news: dict, markets: list[dict]) -> str:
    """Build the match-verification prompt"""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    market_lines = []
    for i, market in enumerate(markets, start=1):
        market_lines.append(f"{i}. {market['question']}")

    market_list = "\n".join(market_lines)

    prompt = f"""You are screening prediction markets for relevance to a news story.

Current date and time: {today}

News story:
Title: {news['title']}
Summary: {news['summary']}
Source: {news['source']}
Published: {news['published']}

Candidate markets:
{market_list}

Task: identify which markets, if any, this news story materially affects.

A market is affected only if this specific news changes the probability that the
market resolves YES. Apply these rules:
- Sharing a topic, region, or named person is NOT enough.
- A chain of speculative steps ("this might lead to X, which might lead to Y") is NOT enough.
- If the news is old or already widely known, it likely changes nothing.
- It is normal and expected for NO markets to be affected. Returning an empty list
is the correct answer most of the time.

On using your own knowledge:
- DO use your general understanding of how the world works — economics, geopolitics,
causal mechanisms — to reason about whether and how this news propagates to a market.
- DO NOT rely on your training data for the current state of affairs. Your knowledge
has a cutoff and is likely outdated. The news text above is your only source for
what is true right now.

Respond with ONLY a JSON object and no other text:
{{"relevant": [1, 3], "reasoning": "one sentence per selected market, or a brief note if none were selected"}}
"""
    
    return prompt


def verify_matches(news:dict, candidates: list[tuple[dict, float]]) -> list[dict]:
    """Ask the LLM which candidate markets are actually affected by this news."""
    if len(candidates) == 0:
        return []
    
    markets = [market for market, score in candidates]
    prompt = build_prompt(news, markets)

    client = get_client()
    response = client.messages.create(
        model = MATCHER_MODEL,
        max_tokens = 500,
        messages = [{"role": "user", "content": prompt}]
    )
    text = response.content[0].text
    text_json = parse_llm_json(text)
    if text_json is None:
        return []
    
    reasoning = text_json.get("reasoning", "")
    if reasoning:
        print(f"  [matcher] {reasoning}")

    relevant_numbers = text_json.get("relevant", [])

    relevant_markets = []
    for num in relevant_numbers:
        index = num - 1
        if 0 <= index < len(markets):
            relevant_markets.append(markets[index])
        
    return relevant_markets

if __name__ == "__main__":
    news = {
        "title": "Families claim bodies of victims of deadly Bangkok pub fire",
        "summary": "Relatives gathered at a morgue in Bangkok to identify victims of a nightclub fire that killed dozens.",
        "source": "Al Jazeera",
        "published": "Tue, 14 Jul 2026 12:00:00 GMT",
    }

    candidates = [
        ({"question": "Will oil hit $100 by November?"}, 0.323),
        ({"question": "Will the U.S. invade Iran before 2027?"}, 0.303),
        ({"question": "Will the Fed cut rates in September?"}, 0.237),
    ]

    print(f"News: {news['title']}\n")
    relevant = verify_matches(news, candidates)
    print(f"\nLLM selected {len(relevant)} relevant market(s):")
    for m in relevant:
        print(f"  - {m['question']}")