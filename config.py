# LLM models
MATCHER_MODEL = "claude-haiku-4-5" # for cheap classification
ANALYZER_MODEL = "claude-sonnet-5" # for reasoning

# Matching thresholds
TOP_K_CANDIDATES = 5
MIN_SIMILARITY = 0.25

# Alert threshold
MIN_DELTA = 0.1
MIN_PRICING_DELAY = 0.4

# Fetch intervals (seconds)
MARKET_REFRESH_INTERVAL = 300   # 5 min
NEWS_CHECK_INTERVAL = 120       # 2 min

# Initial market fetching
INITIAL_LOOKBACK_HOURS = 1
MARKET_FETCH_LIMIT = 500