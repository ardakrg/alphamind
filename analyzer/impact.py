from datetime import datetime
from config import ANALYZER_MODEL
from llm_utils import get_client, parse_llm_json

def build_impact_prompt(news: dict, market: dict) -> str:
    """Build the impact-analysis prompt for a single news-market pair."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""You are estimating how a news story should change a prediction market's probability.

Current date and time: {now}

News story:
Title: {news['title']}
Summary: {news['summary']}
Source: {news['source']}
Published: {news['published']}

Prediction market:
Question: {market['question']}
Current market probability of YES: {market['yes_probability']:.3f}
24h trading volume: ${market['volume_24h']:,.0f}
Order book liquidity: ${market['liquidity']:,.0f}

Work through this in order. Do not skip ahead.

Step 1 — Reason from the news alone.
Before looking at the market price again, ask: given this news and your understanding
of the relevant causal mechanisms, what probability would you assign to YES? Think
about what would have to happen between now and resolution, and how this news changes
that path.

Step 2 — Weigh the market price as evidence.
The market price is the aggregate belief of traders with money at risk. Many of them
know things you do not, and they have been watching this market longer than you.
Treat a large gap between your estimate and the price as a signal that you may be
missing something — not as an obvious mispricing. Move toward the market unless you
can name the specific information the market appears not to have.

Step 3 — Assess whether the market has already priced this in.
Check the publication time against the current time. If hours or days have passed,
traders have likely already reacted and the current price already reflects this news.
Ask also whether the news is genuinely surprising, or a continuation of something
already known. Report this as market_pricing_delay: 1.0 means the market almost
certainly has not reacted yet, 0.0 means it is fully priced in.

Step 4 — State your uncertainty honestly.
confidence reflects how much you trust your own estimate. Reserve values above 0.7 for
cases where the causal link is direct and the news is unambiguous. If you are reasoning
through several steps, or the news is vague, confidence should be low.

On using your own knowledge:
- DO use your general understanding of economics, geopolitics, and causal mechanisms.
- DO NOT rely on your training data for the current state of affairs. Your knowledge has
  a cutoff and is likely outdated. The news text and the market price are your only
  sources for what is true right now.

Respond with ONLY a JSON object and no other text:
{{
  "affects_market": true,
  "new_probability": 0.35,
  "confidence": 0.6,
  "market_pricing_delay": 0.4,
  "reasoning": "2-3 sentences explaining the causal path and why you landed where you did",
  "key_uncertainties": ["what could make this estimate wrong", "..."]
}}
"""

def analyze_impact(news: dict, market: dict) -> dict | None:
    """Ask the LLM how this news should change the market's YES probability."""
    prompt = build_impact_prompt(news, market)
    client = get_client()

    response = client.messages.create(
        model = ANALYZER_MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    text = None
    for block in response.content:
        if block.type == "text":
            text = block.text
            break
    if text is None:
        return None


    text_parsed = parse_llm_json(text)
    if text_parsed is None:
        return None
    
    return text_parsed

if __name__ == "__main__":
    news = {
        "title": "Trump scraps threat of 20% fee on Hormuz cargo as US prepares to resume blockade of Iran ports",
        "summary": "Trump drops a 24-hour-old vow to charge cargo ships for using the Strait as the US continues its battle to break Iran's hold on the waterway.",
        "source": "BBC World",
        "published": "Tue, 14 Jul 2026 16:54:46 GMT",
    }

    market = {
        "question": "Will oil hit $100 by November?",
        "yes_probability": 0.14,
        "volume_24h": 25000,
        "liquidity": 5000,
    }

    result = analyze_impact(news, market)
    if result is None:
        print("Failed to parse LLM response")
    else:
        print(f"Market: {market['question']}")
        print(f"Market price:     {market['yes_probability']:.3f}")
        print(f"LLM estimate:     {result['new_probability']:.3f}")
        print(f"Delta:            {result['new_probability'] - market['yes_probability']:+.3f}")
        print(f"Confidence:       {result['confidence']:.2f}")
        print(f"Pricing delay:    {result['market_pricing_delay']:.2f}")
        print(f"\nReasoning: {result['reasoning']}")
        print(f"\nUncertainties:")
        for u in result.get("key_uncertainties", []):
            print(f"  - {u}")