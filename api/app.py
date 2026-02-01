import json
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ── Paths ────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "processed"
TRENDS_FILE = ROOT / "flattened_trends_data.json"

# ── Geo helper ───────────────────────────────────────────────────────

def country_to_location(country):
    nation_geolocation = {
        'US': (40.592998, -97.989633),
        'CN': (34.125123, 103.323753),
        'JP': (36.180814, 139.391852),
        'DE': (51.718119, 10.134006),
        'IN': (22.252333, 77.842872),
        'GB': (52.509086, -1.156463),
        'FR': (47.322551, 1.907086),
        'IT': (42.442869, 13.275428),
        'BR': (-10.335438, -51.068028),
        'CA': (55.279994, -97.900384),
        'KR': (36.579341, 127.956914),
        'RU': (65.871317, 107.778682),
        'AU': (-25.496731, 133.710404),
        'ES': (39.572586, -3.843935),
        'MX': (22.363872, -101.827129),
        'ID': (-1.057932, 114.677483),
        'NL': (52.133566, 5.237140),
        'SA': (-30.513815, 23.129600),
        'TR': (39.019063, 34.642999),
        'SG': (1.337386, 103.852455),
    }
    return nation_geolocation[country]

COUNTRY_NAMES = {
    "US": "United States", "CN": "China", "JP": "Japan", "DE": "Germany",
    "IN": "India", "GB": "United Kingdom", "FR": "France", "IT": "Italy",
    "BR": "Brazil", "CA": "Canada", "KR": "South Korea", "RU": "Russia",
    "AU": "Australia", "ES": "Spain", "MX": "Mexico", "ID": "Indonesia",
    "NL": "Netherlands", "SA": "South Africa", "TR": "Turkey", "SG": "Singapore",
}

# ── Load data at startup ─────────────────────────────────────────────

with open(DATA_DIR / "tweets_matching_set.json") as f:
    _tweets_matching = json.load(f)

with open(TRENDS_FILE) as f:
    _raw_trends = json.load(f)

# ── Pre-build /commodities ───────────────────────────────────────────

def _build_commodities():
    by_product = defaultdict(list)
    for r in _raw_trends:
        by_product[r["product"]].append(r)

    commodities = []
    for product, records in by_product.items():
        records.sort(key=lambda r: r["timestamp"])

        by_time = defaultdict(float)
        by_country_total = defaultdict(float)
        for r in records:
            by_time[r["timestamp"]] += r["searches"]
            by_country_total[r["country"]] += r["searches"]

        timestamps = sorted(by_time.keys())
        scores = [by_time[t] for t in timestamps]
        if not scores:
            continue

        current_score = int(scores[-1])

        n = len(scores)
        if n >= 5:
            indices = [int(i * (n - 1) / 4) for i in range(5)]
            historical = [int(scores[i]) for i in indices]
        else:
            historical = [int(s) for s in scores]

        split = max(1, n // 5)
        recent_avg = sum(scores[-split:]) / split
        if n >= 2 * split:
            prev_avg = sum(scores[-2 * split:-split]) / split
        else:
            prev_avg = recent_avg
        delta = int(((recent_avg - prev_avg) / max(prev_avg, 1)) * 100)

        top_country = max(by_country_total, key=by_country_total.get)

        commodities.append({
            "name": product.title(),
            "country": COUNTRY_NAMES.get(top_country, top_country),
            "delta": delta,
            "score": current_score,
            "historicalScores": historical,
        })

    commodities.sort(key=lambda c: abs(c["delta"]), reverse=True)
    return commodities

_commodity_items = _build_commodities()

# ── Pre-build /globe ─────────────────────────────────────────────────

def _build_globe():
    counts = defaultdict(int)
    for tweet in _tweets_matching:
        loc = tweet.get("location", "")
        if loc:
            counts[loc] += 1

    if not counts:
        return []

    max_count = max(counts.values())
    points = []
    for country, count in counts.items():
        try:
            lat, lng = country_to_location(country)
        except KeyError:
            continue
        points.append({
            "lat": lat,
            "lng": lng,
            "weight": round(count / max_count, 3),
        })
    return points

_globe_points = _build_globe()

# ── Pre-build /details lookup ─────────────────────────────────────────

def _build_details():
    by_slug = defaultdict(lambda: defaultdict(float))
    for r in _raw_trends:
        slug = r["product"].replace(" ", "-")
        date_str = r["timestamp"][:10]
        by_slug[slug][date_str] += r["searches"]

    lookup = {}
    for slug, date_scores in by_slug.items():
        sorted_dates = sorted(date_scores.keys())
        lookup[slug] = [
            {"date": d, "score": int(date_scores[d])}
            for d in sorted_dates
        ]
    return lookup

_details_lookup = _build_details()

# ── Endpoints ─────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/feed")
def get_feed():
    return {'posts': [
        'We are running out of potatoes',
        'My day has been going well',
        'Hello Nishant :)',
    ]}

@app.get("/shortages")
def get_shortages():
    return {'shortages': [
        {'name': 'potatoes', 'weight': 0.8, 'geolocation': country_to_location("US")},
        {'name': 'bacon', 'weight': 0.2, 'geolocation': country_to_location("GB")}
    ]}

@app.get("/commodities")
def get_commodities():
    return _commodity_items

@app.get("/globe")
def get_globe():
    return _globe_points

@app.get("/details/{slug}")
def get_details(slug: str):
    series = _details_lookup.get(slug)
    if series is None:
        raise HTTPException(status_code=404, detail=f"No data for product: {slug}")
    return series
