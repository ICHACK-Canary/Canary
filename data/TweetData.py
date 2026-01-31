"""
Tweet data acquisition and preprocessing for demand-analyser.

Provides three capabilities:
1. Sentiment classifier trained on Sentiment140 (used to enrich posts)
2. Tweet fetching from scraping APIs (with mock fallback)
3. Multi-layered noise reduction filtering for pre-shortage signals

Output: list of post dicts compatible with the existing pipeline.
"""

import asyncio
import csv
import html
import logging
import os
import re
from datetime import datetime, timezone
from random import sample
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────

# Tier 1: Active buying intent (strongest pre-shortage signals)
TIER1_KEYWORDS = [
    "stock up", "stocking up", "buy extra", "buying extra",
    "bulk buy", "bulk buying", "panic buy", "panic buying",
    "grabbed more", "stockpile", "stockpiling", "hoarding",
]

# Tier 2: Anticipatory concern (weaker but earlier signals)
TIER2_KEYWORDS = [
    "just in case", "before it runs out", "better get some",
    "might run out", "heard there's a shortage",
    "going to be a shortage", "while it's still available",
    "before they're gone", "getting hard to find",
]

EARLY_WARNING_KEYWORDS = TIER1_KEYWORDS + TIER2_KEYWORDS

# Systemic indicators — suggest widespread behavior
SYSTEMIC_INDICATORS = [
    "everywhere", "all stores", "all locations", "whole city",
    "every shop", "nationwide", "across the country", "multiple stores",
    "entire region", "no one can find", "everyone", "whole area",
    "everyone is", "people are",
]

# Individual indicators — suggest isolated behavior
INDIVIDUAL_INDICATORS = [
    "my store", "my local", "one shop", "this location",
    "just me", "near me only", "this branch",
]

MIN_DATE = datetime(2019, 1, 1, tzinfo=timezone.utc)

# Sentiment140 CSV column indices (no header in the original file)
S140_COL_POLARITY = 0
S140_COL_TEXT = 5


# ──────────────────────────────────────────────────────────────
# Text Cleaning
# ──────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """
    Clean tweet text for downstream matching and NLP.

    Removes URLs, @mentions, RT prefixes, extra whitespace, and HTML
    entities. Returns lowercase text suitable for keyword matching.
    """
    text = html.unescape(text)
    text = re.sub(r"^RT\s+@\w+:\s*", "", text)       # RT prefix
    text = re.sub(r"@\w+", "", text)                   # @mentions
    text = re.sub(r"https?://\S+", "", text)            # URLs
    text = re.sub(r"#(\w+)", r"\1", text)               # hashtags → word
    text = re.sub(r"\s+", " ", text).strip()            # collapse whitespace
    return text.lower()


# ──────────────────────────────────────────────────────────────
# Sentiment Classifier (trained on Sentiment140)
# ──────────────────────────────────────────────────────────────

class SentimentClassifier:
    """
    Lightweight sentiment classifier trained on Sentiment140.

    Uses TF-IDF + MultinomialNB. The classifier distinguishes negative (0)
    from positive (4) sentiment. Sentiment140's neutral class (2) is excluded
    per the dataset's convention.

    Used to enrich tweets with a sentiment_score before they enter the
    demand-analyser pipeline. Negative sentiment about products amplifies
    shortage signals.
    """

    def __init__(self):
        self._vectorizer = None
        self._model = None
        self._is_trained = False

    def train(self, sentiment140_path: str, max_rows: int = 100_000) -> None:
        """
        Train classifier on Sentiment140 CSV.

        Args:
            sentiment140_path: Path to the Sentiment140 CSV file.
            max_rows: Subsample size for faster training. 100k gives ~80%
                accuracy which is sufficient for this use case.
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.naive_bayes import MultinomialNB

        texts, labels = [], []
        with open(sentiment140_path, encoding="latin-1") as f:
            reader = csv.reader(f)
            for row in reader:
                polarity = int(row[S140_COL_POLARITY])
                if polarity not in (0, 4):
                    continue
                texts.append(row[S140_COL_TEXT])
                labels.append(0 if polarity == 0 else 1)

        # Subsample for speed
        if len(texts) > max_rows:
            indices = sample(range(len(texts)), max_rows)
            texts = [texts[i] for i in indices]
            labels = [labels[i] for i in indices]

        logger.info(f"Training sentiment classifier on {len(texts)} samples")

        self._vectorizer = TfidfVectorizer(max_features=20_000, ngram_range=(1, 2))
        X = self._vectorizer.fit_transform(texts)

        self._model = MultinomialNB()
        self._model.fit(X, labels)
        self._is_trained = True

        logger.info("Sentiment classifier training complete")

    def predict_sentiment(self, text: str) -> float:
        """
        Return sentiment score for a single text.

        Returns:
            Float in [0.0, 1.0] where 0.0 = strong negative,
            1.0 = strong positive. Returns 0.5 if untrained.
        """
        if not self._is_trained:
            return 0.5

        X = self._vectorizer.transform([text])
        proba = self._model.predict_proba(X)[0]
        # Index 1 is the positive class probability
        return float(proba[1])

    def save(self, path: str) -> None:
        """Persist trained model to disk using joblib."""
        import joblib
        joblib.dump({
            "vectorizer": self._vectorizer,
            "model": self._model,
        }, path)
        logger.info(f"Sentiment model saved to {path}")

    def load(self, path: str) -> None:
        """Load a previously trained model from disk."""
        import joblib
        data = joblib.load(path)
        self._vectorizer = data["vectorizer"]
        self._model = data["model"]
        self._is_trained = True
        logger.info(f"Sentiment model loaded from {path}")


# ──────────────────────────────────────────────────────────────
# Layer 1: Keyword Filter (predictive pre-shortage signals)
# ──────────────────────────────────────────────────────────────

def _passes_keyword_filter(text: str) -> Tuple[bool, int, List[str]]:
    """
    Check if text contains early-warning keywords.

    Returns:
        (passes, tier, matched_keywords) where tier is 1 (active buying
        intent) or 2 (anticipatory concern). Returns (False, 0, []) if
        no keywords match.
    """
    t = text.lower()
    matched = []
    best_tier = 0

    for kw in TIER1_KEYWORDS:
        if kw in t:
            matched.append(kw)
            best_tier = 1

    for kw in TIER2_KEYWORDS:
        if kw in t:
            matched.append(kw)
            if best_tier == 0:
                best_tier = 2

    return (len(matched) > 0, best_tier, matched)


# ──────────────────────────────────────────────────────────────
# Layer 2: Contextual Filter (systemic vs individual)
# ──────────────────────────────────────────────────────────────

def _contextual_score(text: str) -> float:
    """
    Score how likely a tweet describes systemic behavior vs individual.

    Returns:
        Float in [-1.0, 1.0]:
          positive = systemic signal (widespread hoarding/concern)
          near zero = ambiguous
          negative = isolated individual behavior
    """
    t = text.lower()
    score = 0.0

    for indicator in SYSTEMIC_INDICATORS:
        if indicator in t:
            score += 0.3

    for indicator in INDIVIDUAL_INDICATORS:
        if indicator in t:
            score -= 0.4

    # Temporal urgency amplifiers
    if re.search(r"\b(this week|today|right now|currently|still)\b", t):
        score += 0.1

    return max(-1.0, min(1.0, score))


def _passes_contextual_filter(text: str, threshold: float = -0.3) -> bool:
    """
    Returns True if contextual score is above threshold.

    Default threshold is permissive (-0.3), keeping ambiguous tweets
    and only removing clearly individual complaints.
    """
    return _contextual_score(text) >= threshold


# ──────────────────────────────────────────────────────────────
# Layer 3: Product Category Filter (via concept_mapper)
# ──────────────────────────────────────────────────────────────

def _passes_product_filter(
    text: str, concept_mapper_fn=None
) -> Tuple[bool, Optional[str]]:
    """
    Check if the tweet mentions a known product category.

    Args:
        text: Tweet text.
        concept_mapper_fn: The map_to_product function from
            processing/concept_mapper.py. Passed as parameter to avoid
            circular imports and import-time crashes.

    Returns:
        (passes, product_name). If no mapper provided, passes everything.
    """
    if concept_mapper_fn is None:
        return (True, None)

    product = concept_mapper_fn(text)
    return (product is not None, product)


# ──────────────────────────────────────────────────────────────
# Combined Filter Pipeline
# ──────────────────────────────────────────────────────────────

def filter_tweets(
    tweets: List[Dict],
    concept_mapper_fn=None,
    require_product_match: bool = False,
    contextual_threshold: float = -0.3,
) -> List[Dict]:
    """
    Apply all three noise reduction layers to a list of tweets.

    Each passing tweet is enriched with:
      - keywords_matched: list of matched early-warning keywords
      - keyword_tier: 1 (buying intent) or 2 (anticipatory concern)
      - contextual_score: float, systemic vs individual
      - matched_product: str or None

    Args:
        tweets: List of dicts with at least a "text" key.
        concept_mapper_fn: Optional product mapper function.
        require_product_match: If True, tweets must match a known product.
        contextual_threshold: Minimum contextual score (default -0.3).
    """
    filtered = []

    for tweet in tweets:
        text = tweet.get("text", "")

        # Layer 1: Keyword filter
        passes_kw, tier, matched_kws = _passes_keyword_filter(text)
        if not passes_kw:
            continue

        # Layer 2: Contextual filter
        ctx_score = _contextual_score(text)
        if ctx_score < contextual_threshold:
            continue

        # Layer 3: Product category filter
        has_product, product_name = _passes_product_filter(
            text, concept_mapper_fn
        )
        if require_product_match and not has_product:
            continue

        # Enrich
        enriched = dict(tweet)
        enriched["keywords_matched"] = matched_kws
        enriched["keyword_tier"] = tier
        enriched["contextual_score"] = ctx_score
        enriched["matched_product"] = product_name

        filtered.append(enriched)

    logger.info(f"Filtered {len(tweets)} -> {len(filtered)} tweets")
    return filtered


# ──────────────────────────────────────────────────────────────
# Temporal Filter
# ──────────────────────────────────────────────────────────────

def filter_by_date(
    tweets: List[Dict],
    since: datetime = None,
    until: datetime = None,
) -> List[Dict]:
    """
    Strictly filter tweets to a date range.

    Defaults to MIN_DATE (2019-01-01) through now.
    """
    since = since or MIN_DATE
    until = until or datetime.now(timezone.utc)

    result = []
    for tweet in tweets:
        ts = tweet.get("timestamp")
        if ts is None:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if since <= ts <= until:
            result.append(tweet)

    return result


# ──────────────────────────────────────────────────────────────
# Location Filter
# ──────────────────────────────────────────────────────────────

def filter_by_location(
    tweets: List[Dict],
    locations: List[str] = None,
    regions: List[str] = None,
    region_resolver_fn=None,
) -> List[Dict]:
    """
    Filter tweets by geographic location.

    Supports two modes that can be combined:
      - locations: match against raw user_location strings
        (case-insensitive, e.g. ["Manchester", "Leeds"])
      - regions: match against resolved region codes
        (e.g. ["UK_NORTH_WEST", "UK_YORKSHIRE"]), requires
        region_resolver_fn to map user_location -> region code

    If both are provided, a tweet passes if it matches either.
    If neither is provided, all tweets pass through unchanged.

    Args:
        tweets: List of dicts with a "user_location" key.
        locations: Raw location strings to include.
        regions: Region codes to include.
        region_resolver_fn: The resolve_region function from
            processing/region_resolver.py. Required when filtering
            by regions.
    """
    if not locations and not regions:
        return tweets

    locations_lower = {loc.lower() for loc in locations} if locations else set()
    regions_upper = {r.upper() for r in regions} if regions else set()

    result = []
    for tweet in tweets:
        user_loc = tweet.get("user_location", "")

        # Check raw location match
        if locations_lower and user_loc.lower() in locations_lower:
            result.append(tweet)
            continue

        # Check resolved region match
        if regions_upper and region_resolver_fn is not None:
            resolved = region_resolver_fn(user_loc)
            if resolved and resolved.upper() in regions_upper:
                result.append(tweet)
                continue

    return result


# ──────────────────────────────────────────────────────────────
# Tweet Fetching
# ──────────────────────────────────────────────────────────────

class TweetFetchError(Exception):
    """Raised when tweet scraping fails."""
    pass


COOKIES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "twikit_cookies.json"
)


async def _fetch_via_twikit(
    query: str,
    max_results: int,
    cookies_path: str = None,
) -> List[Dict]:
    """
    Fetch tweets using twikit (authenticated mode).

    Requires a prior login that saved cookies, OR credentials in
    environment variables X_USERNAME, X_EMAIL, X_PASSWORD.

    First run: set env vars, twikit logs in and saves cookies.
    Subsequent runs: loads cookies automatically (no re-login).
    """
    from twikit import Client

    cookies_path = cookies_path or COOKIES_PATH
    client = Client(language="en-US")

    # Try loading saved cookies first
    if os.path.exists(cookies_path):
        client.load_cookies(cookies_path)
        logger.info("Loaded twikit cookies from disk")
    else:
        # Login with credentials from env vars
        username = os.environ.get("X_USERNAME")
        email = os.environ.get("X_EMAIL")
        password = os.environ.get("X_PASSWORD")

        if not all([username, email, password]):
            raise TweetFetchError(
                "No twikit cookies found and X_USERNAME / X_EMAIL / "
                "X_PASSWORD env vars not set. Run the login flow first:\n"
                "  export X_USERNAME='your_handle'\n"
                "  export X_EMAIL='your_email'\n"
                "  export X_PASSWORD='your_password'\n"
                "Then call fetch_tweets() — cookies will be saved for future runs."
            )

        await client.login(
            auth_info_1=username,
            auth_info_2=email,
            password=password,
        )
        client.save_cookies(cookies_path)
        logger.info(f"Logged in and saved cookies to {cookies_path}")

    # Search tweets (twikit returns max 20 per page, paginate)
    tweets = []
    cursor = None
    while len(tweets) < max_results:
        batch = await client.search_tweet(
            query, product="Latest", count=20, cursor=cursor
        )
        if not batch:
            break
        for tweet in batch:
            tweets.append({
                "text": tweet.text or "",
                "timestamp": datetime.strptime(
                    tweet.created_at, "%a %b %d %H:%M:%S %z %Y"
                ) if tweet.created_at else datetime.now(timezone.utc),
                "user_location": (tweet.user.location or "") if tweet.user else "",
                "tweet_id": tweet.id,
                "username": tweet.user.screen_name if tweet.user else "",
                "retweet_count": tweet.retweet_count or 0,
                "like_count": tweet.favorite_count or 0,
            })
        if not hasattr(batch, "next") or batch.next is None:
            break
        try:
            cursor = batch.next_cursor
        except AttributeError:
            break

    return tweets[:max_results]


def fetch_tweets_scraper(
    keywords: List[str] = None,
    since: datetime = None,
    until: datetime = None,
    max_results: int = 500,
    lang: str = "en",
    cookies_path: str = None,
) -> List[Dict]:
    """
    Fetch recent tweets using twikit (primary).

    Requires either:
      - Saved cookies at config/twikit_cookies.json (from a prior login)
      - Environment variables: X_USERNAME, X_EMAIL, X_PASSWORD

    Returns list of dicts matching the pipeline schema:
        {"text": str, "timestamp": datetime, "user_location": str}
    """
    keywords = keywords or EARLY_WARNING_KEYWORDS[:6]
    since = since or MIN_DATE
    until = until or datetime.now(timezone.utc)

    query_terms = " OR ".join(f'"{kw}"' for kw in keywords)
    since_str = since.strftime("%Y-%m-%d")
    until_str = until.strftime("%Y-%m-%d")
    query = f"({query_terms}) lang:{lang} since:{since_str} until:{until_str}"

    try:
        tweets = asyncio.run(
            _fetch_via_twikit(query, max_results, cookies_path)
        )
        if tweets:
            return tweets
    except TweetFetchError:
        raise
    except Exception as e:
        logger.warning(f"twikit failed: {e}")

    raise TweetFetchError(
        "twikit scraping failed. Ensure you have valid credentials.\n"
        "Use fetch_tweets(use_mock=True) for development."
    )


def fetch_tweets_mock(count: int = 50) -> List[Dict]:
    """
    Return synthetic tweets for development and testing.

    Covers: pre-shortage buying intent, individual vs systemic hoarding,
    off-topic noise, and various product categories.
    """
    MOCK_TWEETS = [
        # Tier 1 — Active buying intent (systemic)
        {
            "text": "Everyone is stocking up on rice and pasta, shelves getting thin everywhere",
            "timestamp": datetime(2025, 11, 15, 14, 30, tzinfo=timezone.utc),
            "user_location": "Manchester",
        },
        {
            "text": "Panic buying toilet roll again, all stores in Leeds running low",
            "timestamp": datetime(2025, 11, 15, 15, 0, tzinfo=timezone.utc),
            "user_location": "Leeds",
        },
        {
            "text": "People are bulk buying flour and bread nationwide right now",
            "timestamp": datetime(2025, 11, 16, 9, 0, tzinfo=timezone.utc),
            "user_location": "Manchester",
        },
        {
            "text": "Grabbed more canned goods and eggs today, stockpiling just in case",
            "timestamp": datetime(2025, 11, 16, 11, 0, tzinfo=timezone.utc),
            "user_location": "Leeds",
        },
        {
            "text": "Stocking up on baby formula while it's still available everywhere",
            "timestamp": datetime(2025, 11, 16, 13, 0, tzinfo=timezone.utc),
            "user_location": "Manchester",
        },
        {
            "text": "Hoarding hand sanitiser again, entire region is doing it",
            "timestamp": datetime(2025, 11, 17, 8, 0, tzinfo=timezone.utc),
            "user_location": "Leeds",
        },
        {
            "text": "Bulk buying milk and eggs, every shop is seeing this",
            "timestamp": datetime(2025, 11, 17, 10, 0, tzinfo=timezone.utc),
            "user_location": "Manchester",
        },
        # Tier 1 — Active buying intent (individual — should be downweighted)
        {
            "text": "I'm stocking up on pasta at my local shop just me being cautious",
            "timestamp": datetime(2025, 11, 15, 16, 0, tzinfo=timezone.utc),
            "user_location": "Leeds",
        },
        {
            "text": "Grabbed more bread from my store, panic buy mode activated",
            "timestamp": datetime(2025, 11, 15, 17, 0, tzinfo=timezone.utc),
            "user_location": "Manchester",
        },
        # Tier 2 — Anticipatory concern (systemic)
        {
            "text": "Heard there's a shortage of rice coming, better get some before it runs out",
            "timestamp": datetime(2025, 11, 17, 12, 0, tzinfo=timezone.utc),
            "user_location": "Manchester",
        },
        {
            "text": "Flour might run out soon, getting hard to find in multiple stores",
            "timestamp": datetime(2025, 11, 17, 14, 0, tzinfo=timezone.utc),
            "user_location": "Leeds",
        },
        {
            "text": "Better get some toilet paper before they're gone, whole city seems worried",
            "timestamp": datetime(2025, 11, 18, 9, 0, tzinfo=timezone.utc),
            "user_location": "Manchester",
        },
        {
            "text": "Baby formula getting hard to find, people are worried everywhere",
            "timestamp": datetime(2025, 11, 18, 11, 0, tzinfo=timezone.utc),
            "user_location": "Leeds",
        },
        {
            "text": "Just in case the supply issues get worse, buying extra eggs and milk today",
            "timestamp": datetime(2025, 11, 18, 14, 0, tzinfo=timezone.utc),
            "user_location": "Manchester",
        },
        # Tier 2 — Anticipatory concern (individual)
        {
            "text": "Might run out of bread, grabbing extra from my local just in case",
            "timestamp": datetime(2025, 11, 18, 16, 0, tzinfo=timezone.utc),
            "user_location": "Leeds",
        },
        {
            "text": "Getting hard to find good pasta near me only, going to stock up just in case",
            "timestamp": datetime(2025, 11, 18, 18, 0, tzinfo=timezone.utc),
            "user_location": "Manchester",
        },
        # Off-topic — should be FILTERED OUT (no shortage keywords)
        {
            "text": "Just made a lovely pasta carbonara for dinner!",
            "timestamp": datetime(2025, 11, 15, 19, 0, tzinfo=timezone.utc),
            "user_location": "Manchester",
        },
        {
            "text": "New bread recipe turned out great today",
            "timestamp": datetime(2025, 11, 16, 19, 0, tzinfo=timezone.utc),
            "user_location": "Leeds",
        },
        {
            "text": "Milk prices are stable this month, no change expected",
            "timestamp": datetime(2025, 11, 17, 19, 0, tzinfo=timezone.utc),
            "user_location": "Manchester",
        },
        {
            "text": "Bought a nice gift for my mum's birthday",
            "timestamp": datetime(2025, 11, 18, 19, 0, tzinfo=timezone.utc),
            "user_location": "Leeds",
        },
        {
            "text": "The weather in Leeds has been terrible this week",
            "timestamp": datetime(2025, 11, 19, 8, 0, tzinfo=timezone.utc),
            "user_location": "Leeds",
        },
        {
            "text": "Stocking up on Christmas decorations, love this time of year",
            "timestamp": datetime(2025, 11, 19, 10, 0, tzinfo=timezone.utc),
            "user_location": "Manchester",
        },
        # Edge cases — contain keywords but no product (Layer 3 test)
        {
            "text": "People are panic buying concert tickets everywhere",
            "timestamp": datetime(2025, 11, 19, 12, 0, tzinfo=timezone.utc),
            "user_location": "Manchester",
        },
        {
            "text": "Hoarding vintage vinyl records, stockpiling before prices rise",
            "timestamp": datetime(2025, 11, 19, 14, 0, tzinfo=timezone.utc),
            "user_location": "Leeds",
        },
        # Pre-2019 — should be filtered by temporal filter
        {
            "text": "Stocking up on rice just in case, everyone is doing it",
            "timestamp": datetime(2018, 3, 10, 12, 0, tzinfo=timezone.utc),
            "user_location": "Manchester",
        },
        # Additional variety for volume
        {
            "text": "Stockpiling canned goods, heard there's a shortage coming to all locations",
            "timestamp": datetime(2025, 11, 20, 8, 0, tzinfo=timezone.utc),
            "user_location": "Leeds",
        },
        {
            "text": "Buying extra hand sanitiser while it's still available, every shop has less",
            "timestamp": datetime(2025, 11, 20, 9, 0, tzinfo=timezone.utc),
            "user_location": "Manchester",
        },
        {
            "text": "Bulk buying noodles and rice, going to be a shortage for sure",
            "timestamp": datetime(2025, 11, 20, 10, 0, tzinfo=timezone.utc),
            "user_location": "Leeds",
        },
        {
            "text": "Stocking up on tinned goods before they're gone, nationwide panic",
            "timestamp": datetime(2025, 11, 20, 11, 0, tzinfo=timezone.utc),
            "user_location": "Manchester",
        },
        {
            "text": "People are stockpiling eggs again, all stores low",
            "timestamp": datetime(2025, 11, 20, 12, 0, tzinfo=timezone.utc),
            "user_location": "Leeds",
        },
    ]
    return MOCK_TWEETS[:count]


def fetch_tweets(
    keywords: List[str] = None,
    use_mock: bool = False,
    **kwargs,
) -> List[Dict]:
    """
    Unified entry point for tweet fetching.

    Tries live scraping first; raises TweetFetchError if scraping fails
    and use_mock is False.
    """
    if use_mock:
        return fetch_tweets_mock()

    keywords = keywords or EARLY_WARNING_KEYWORDS[:6]
    return fetch_tweets_scraper(keywords, **kwargs)


# ──────────────────────────────────────────────────────────────
# Pipeline Integration
# ──────────────────────────────────────────────────────────────

def prepare_tweets_for_pipeline(
    tweets: List[Dict] = None,
    use_mock: bool = True,
    sentiment_classifier: SentimentClassifier = None,
    concept_mapper_fn=None,
    require_product_match: bool = False,
    locations: List[str] = None,
    regions: List[str] = None,
    region_resolver_fn=None,
) -> List[Dict]:
    """
    Full pipeline: fetch -> clean -> temporal filter -> location filter
    -> noise reduction -> sentiment enrichment.

    Returns dicts compatible with the downstream pipeline:
        {
            "text": str,               # cleaned text
            "original_text": str,      # raw text before cleaning
            "timestamp": datetime,
            "user_location": str,
            "sentiment_score": float,  # from Sentiment140 classifier
            "contextual_score": float, # systemic vs individual
            "keyword_tier": int,       # 1 or 2
            "keywords_matched": list,  # which keywords hit
            "matched_product": str | None,
        }

    Args:
        tweets: Pre-fetched tweets. If None, fetches new tweets.
        use_mock: Use mock data for fetching (default True).
        sentiment_classifier: Trained SentimentClassifier instance.
        concept_mapper_fn: map_to_product function.
        require_product_match: Require product category match.
        locations: Filter to these raw location strings
            (e.g. ["Manchester", "Leeds"]).
        regions: Filter to these region codes
            (e.g. ["UK_NORTH_WEST"]). Requires region_resolver_fn.
        region_resolver_fn: The resolve_region function from
            processing/region_resolver.py.
    """
    # Step 1: Fetch
    if tweets is None:
        tweets = fetch_tweets(use_mock=use_mock)

    # Step 2: Clean text (preserve original)
    for tweet in tweets:
        tweet["original_text"] = tweet["text"]
        tweet["text"] = clean_text(tweet["text"])

    # Step 3: Temporal filter
    tweets = filter_by_date(tweets)

    # Step 4: Location filter
    tweets = filter_by_location(
        tweets,
        locations=locations,
        regions=regions,
        region_resolver_fn=region_resolver_fn,
    )

    # Step 5: Multi-layered noise reduction
    tweets = filter_tweets(
        tweets,
        concept_mapper_fn=concept_mapper_fn,
        require_product_match=require_product_match,
    )

    # Step 6: Sentiment enrichment
    for tweet in tweets:
        if sentiment_classifier is not None:
            tweet["sentiment_score"] = sentiment_classifier.predict_sentiment(
                tweet["text"]
            )
        else:
            tweet["sentiment_score"] = 0.5

    return tweets