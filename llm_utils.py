import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

_client = None

def get_client() -> anthropic.Anthropic:
    """Lazy-load the Anhtropic client"""
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client

def parse_llm_json(text: str) -> dict | None:
    """Extract and parse JSON from an LLM response, tolerating code fences."""
    text = text.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    
    try:
        text_json = json.loads(text)
    except json.JSONDecodeError:
        return None

    return text_json