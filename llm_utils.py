import json
import anthropic
from dotenv import load_dotenv
from config import MODEL_PRICES, WEB_SEARCH_PRICE

load_dotenv()

_client = None

def get_client() -> anthropic.Anthropic:
    """Lazy-load the Anhtropic client"""
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client

usage_totals = {}   # model -> calls / input_tokens / output_tokens / web_searches, since the last daily report

def record_usage(response):
    """Add one API response's tokens and searches to the running totals, under the model that served it."""
    totals = usage_totals.setdefault(response.model, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "web_searches": 0})
    totals["calls"] += 1
    totals["input_tokens"] += response.usage.input_tokens
    totals["output_tokens"] += response.usage.output_tokens
    server_tools = getattr(response.usage, "server_tool_use", None)
    if server_tools is not None:
        totals["web_searches"] += server_tools.web_search_requests or 0

def usage_cost(model: str, totals: dict) -> float | None:
    """USD cost of a model's totals, or None if the model has no price in config."""
    if model not in MODEL_PRICES:
        return None
    input_price, output_price = MODEL_PRICES[model]
    return (totals["input_tokens"] * input_price + totals["output_tokens"] * output_price) / 1e6 \
        + totals["web_searches"] * WEB_SEARCH_PRICE

def truncate_middle(text: str, limit: int) -> str:
    """Shorten text to about `limit` chars, keeping the first 60% and the last 40%."""
    if len(text) <= limit:
        return text
    head = int(limit * 0.6)
    tail = limit - head
    return text[:head].rstrip() + " … " + text[-tail:].lstrip()

def extract_text(response) -> str:
    """The text of the model's final answer.

    With server tools (web search) the content interleaves text, server_tool_use and
    *_tool_result blocks, and one answer can be split over several text blocks
    (e.g. around citations). Thinking blocks are skipped. Only text after the last
    tool result counts, unless there is none there.
    """
    blocks = list(response.content)
    last_result = max((i for i, b in enumerate(blocks) if b.type.endswith("_tool_result")), default=-1)

    text = "".join(b.text for b in blocks[last_result + 1:] if b.type == "text")
    if not text.strip():
        text = "".join(b.text for b in blocks if b.type == "text")
    return text

def parse_llm_json(text: str) -> dict | None:
    """Find the JSON object in an LLM response, tolerating code fences and surrounding prose.

    If there are several top-level objects, the last one wins. Prints the raw text
    when nothing parses, so failures are visible in the log.
    """
    decoder = json.JSONDecoder()
    parsed = None
    i = text.find("{")
    while i != -1:
        try:
            obj, end = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            i = text.find("{", i + 1)
            continue
        if isinstance(obj, dict):
            parsed = obj
        i = text.find("{", end)

    if parsed is None:
        print(f"  [parse-failed] could not find JSON in LLM response:\n{text!r}")
    return parsed
