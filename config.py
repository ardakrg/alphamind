# LLM models
MATCHER_MODEL = "claude-haiku-5-5" # for cheap classification
ANALYZER_MODEL = "claude-sonnet-5-5" # for reasoning
WEB_SEARCH_MAX_USES = 4           # max web searches per verification (second-pass) analyzer call
SEARCH_FAILED_MAX_CONFIDENCE = 0.3  # confidence cap when the analyzer couldn't verify via search

# API prices for the daily cost summary, USD per million tokens (input, output). From
# platform.claude.com/docs/en/about-claude/pricing, 2026-10-20. Haiku 5.5 doubles to $0.50/$2.50
# above 100K prompt tokens; our prompts stay far below that. Sonnet 5 is the fallback model.
MODEL_PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
}
WEB_SEARCH_PRICE = 0.01   # USD per search ($10 per 1,000)

# Market descriptions in prompts (long ones keep the start and the end, where the resolution rules sit)
DESCRIPTION_MAX_CHARS = 1000         # stored in the market dict, shown to the analyzer
MATCHER_DESCRIPTION_MAX_CHARS = 300  # per candidate in the matcher prompt

# Matching thresholds
TOP_K_CANDIDATES = 5
MIN_SIMILARITY = 0.25

# Alert threshold
MIN_DELTA = 0.1
MIN_PRICING_DELAY = 0.4
MAX_DELTA = 0.40              # |LLM estimate - market price| above this is rejected as a likely misread

# Cooldowns
ANALYSIS_COOLDOWN_HOURS = 3   # don't analyze the same market again within this window (in memory)
REALERT_WINDOW_HOURS = 24     # a market alerted within this window only re-alerts on a real change:
REALERT_MIN_CHANGE = 0.15     # direction flipped, or LLM estimate moved at least this much

# Fetch intervals (seconds)
MARKET_REFRESH_INTERVAL = 300   # 5 min
NEWS_CHECK_INTERVAL = 120       # 2 min

# Initial market fetching
INITIAL_LOOKBACK_HOURS = 1
MARKET_FETCH_LIMIT = 500

# Alert evaluation
WATCHLIST_HOURS = 48              # keep storing prices for alerted markets this long after the alert
SNAPSHOT_TOLERANCE_MINUTES = 15   # max distance between a horizon (+1h/+6h/+24h) and the snapshot used for it
