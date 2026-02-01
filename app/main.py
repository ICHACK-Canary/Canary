from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
import json
import os
import random
import subprocess
import threading
import tempfile

app = FastAPI(title="Demand Analyser API")

# Enable CORS for all origins, methods, and headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# CONFIGURATION & DATA
# =============================================================================

NATION_GEOLOCATION = {
    'US': {"lat": 40.592998, "lng": -97.989633, "name": "United States"},
    'CN': {"lat": 34.125123, "lng": 103.323753, "name": "China"},
    'JP': {"lat": 36.180814, "lng": 139.391852, "name": "Japan"},
    'DE': {"lat": 51.718119, "lng": 10.134006, "name": "Germany"},
    'IN': {"lat": 22.252333, "lng": 77.842872, "name": "India"},
    'GB': {"lat": 52.509086, "lng": -1.156463, "name": "United Kingdom"},
    'FR': {"lat": 47.322551, "lng": 1.907086, "name": "France"},
    'IT': {"lat": 42.442869, "lng": 13.275428, "name": "Italy"},
    'BR': {"lat": -10.335438, "lng": -51.068028, "name": "Brazil"},
    'CA': {"lat": 55.279994, "lng": -97.900384, "name": "Canada"},
    'KR': {"lat": 36.579341, "lng": 127.956914, "name": "South Korea"},
    'RU': {"lat": 65.871317, "lng": 107.778682, "name": "Russia"},
    'AU': {"lat": -25.496731, "lng": 133.710404, "name": "Australia"},
    'ES': {"lat": 39.572586, "lng": -3.843935, "name": "Spain"},
    'MX': {"lat": 22.363872, "lng": -101.827129, "name": "Mexico"},
    'ID': {"lat": -1.057932, "lng": 114.677483, "name": "Indonesia"},
    'NL': {"lat": 52.133566, "lng": 5.237140, "name": "Netherlands"},
    'SA': {"lat": 24.711667, "lng": 46.724167, "name": "Saudi Arabia"},
    'TR': {"lat": 39.019063, "lng": 34.642999, "name": "Turkey"},
    'SG': {"lat": 1.337386, "lng": 103.852455, "name": "Singapore"},
    'AE': {"lat": 24.453884, "lng": 54.377344, "name": "UAE"},
    'EG': {"lat": 26.820553, "lng": 30.802498, "name": "Egypt"},
}

# Products we're tracking
TRACKED_PRODUCTS = [
    "toilet paper", "hand sanitizer", "rice", "pasta", "flour", "bread",
    "milk", "eggs", "canned beans", "canned soup", "canned vegetables",
    "bottled water", "disinfectant wipes", "frozen vegetables", "frozen pizza",
    "chicken breast", "ground beef", "butter", "cheese", "coffee", "tea",
    "sugar", "salt", "cooking oil", "breakfast cereal", "apples", "bananas",
    "oranges", "potatoes", "onions", "tomatoes", "carrots", "cucumbers",
    "fresh lettuce"
]

# Base path for data files
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# In-memory stores
alerts_store: List[Dict[str, Any]] = []
severity_store: Dict[tuple, Dict[str, Any]] = {}
TWEETS: List[Dict] = []

# Analysis subprocess state
_analysis_process: Optional[subprocess.Popen] = None
_analysis_thread: Optional[threading.Thread] = None
_analysis_status: Dict[str, Any] = {"running": False, "alerts_ingested": 0}

# =============================================================================
# DATA LOADING
# =============================================================================

def get_data_path(relative_path: str) -> str:
    """Get absolute path for a data file."""
    return os.path.join(BASE_DIR, relative_path)

def load_tweets() -> List[Dict]:
    """Load social media posts for matching with alerts."""
    paths = [
        get_data_path("data/processed/tweets_filtered.json"),
        get_data_path("data/tweets.json"),
    ]
    
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    print(f"Loaded {len(data)} tweets from {path}")
                    return data
            except Exception as e:
                print(f"Error loading tweets from {path}: {e}")
    
    print("No tweets file found")
    return []

def load_alerts_from_ndjson(path: str) -> List[Dict]:
    """Load alerts from the Rust analyzer NDJSON output."""
    alerts = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            alerts.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            print(f"Loaded {len(alerts)} alerts from {path}")
        except Exception as e:
            print(f"Error loading alerts: {e}")
    return alerts

def refresh_alerts(alerts_path: str | None = None):
    """Refresh alerts from file and update stores."""
    global alerts_store, severity_store
    
    if alerts_path is None:
        candidates = [
            get_data_path("processing/alerts.ndjson"),
            get_data_path("alerts.ndjson"),
        ]
        for p in candidates:
            if os.path.exists(p):
                alerts_path = p
                break
    
    if alerts_path and os.path.exists(alerts_path):
        alerts_store = load_alerts_from_ndjson(alerts_path)
        
        # Update severity store with latest per (country, product)
        severity_store.clear()
        for alert in alerts_store:
            key = (alert.get("country"), alert.get("product"))
            existing = severity_store.get(key)
            if existing is None or alert.get("timestamp", "") > existing.get("timestamp", ""):
                severity_store[key] = alert
        
        print(f"Refreshed: {len(alerts_store)} alerts, {len(severity_store)} unique series")

# =============================================================================
# STARTUP
# =============================================================================

@app.on_event("startup")
def startup_event():
    """Load data on startup."""
    global TWEETS
    TWEETS = load_tweets()
    refresh_alerts()

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def country_to_location(country: str) -> tuple:
    """Legacy function for backwards compatibility."""
    geo = NATION_GEOLOCATION.get(country, {"lat": 0, "lng": 0})
    return (geo["lat"], geo["lng"])

def get_country_info(country: str) -> Dict:
    """Get full country info including coordinates."""
    return NATION_GEOLOCATION.get(country, {"lat": 0, "lng": 0, "name": country})

def find_matching_tweets(product: str, country: str, limit: int = 5) -> List[Dict]:
    """Find tweets that match a product/country alert."""
    matches = []
    product_lower = product.lower()
    product_words = set(product_lower.split())
    
    for tweet in TWEETS:
        text_lower = tweet.get("text", "").lower()
        location = tweet.get("user_location", "").upper()
        
        # Check if product mentioned (partial match)
        product_match = (
            product_lower in text_lower or
            any(word in text_lower for word in product_words if len(word) > 3)
        )
        
        if product_match:
            # Loose country matching
            country_name = NATION_GEOLOCATION.get(country, {}).get("name", "").upper()
            country_match = (
                country in location or
                country_name in location or
                not location  # Include if no location specified
            )
            if country_match:
                matches.append(tweet)
                if len(matches) >= limit:
                    break
    
    return matches

def severity_to_level(accel_z: float, severity: str) -> Dict:
    """Convert metrics to a severity level."""
    if severity == "CONFIRMED":
        if accel_z >= 10:
            return {"level": "CRITICAL", "score": 100, "color": "#dc2626"}
        else:
            return {"level": "HIGH", "score": 75, "color": "#ea580c"}
    elif severity == "EARLY":
        if accel_z >= 5:
            return {"level": "ELEVATED", "score": 50, "color": "#ca8a04"}
        else:
            return {"level": "WATCH", "score": 25, "color": "#2563eb"}
    return {"level": "NORMAL", "score": 0, "color": "#16a34a"}

def time_ago(timestamp: str) -> str:
    """Convert ISO timestamp to human-readable 'time ago'."""
    try:
        if not timestamp:
            return "unknown"
        ts = timestamp.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.utcnow()
        delta = now - dt.replace(tzinfo=None) if dt.tzinfo else now - dt
        
        days = delta.days
        seconds = delta.seconds
        
        if days < 0:
            return "in the future"
        elif days > 365:
            return f"{days // 365} years ago"
        elif days > 30:
            return f"{days // 30} months ago"
        elif days > 0:
            return f"{days} days ago"
        elif seconds > 3600:
            return f"{seconds // 3600} hours ago"
        elif seconds > 60:
            return f"{seconds // 60} minutes ago"
        else:
            return "just now"
    except Exception:
        return "unknown"

# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.get("/")
def read_root():
    return {
        "service": "Demand Analyser API",
        "version": "1.0.0",
        "endpoints": {
            "alerts": "/alerts - Get alerts with full details",
            "alerts_geojson": "/alerts/geojson - GeoJSON for map",
            "severity": "/severity - Live severity ratings",
            "feed": "/feed - Social media feed",
            "shortages": "/shortages - Legacy GeoJSON endpoint",
            "products": "/products - List tracked products",
            "countries": "/countries - List tracked countries",
            "analysis_start": "/analysis/start - Start Rust anomaly detector",
            "analysis_status": "/analysis/status - Check analysis progress",
            "analysis_stop": "/analysis/stop - Stop running analysis",
        },
        "stats": {
            "alerts_loaded": len(alerts_store),
            "tweets_loaded": len(TWEETS),
            "series_tracked": len(severity_store),
        }
    }

@app.post("/alerts/refresh")
def refresh_alerts_endpoint(path: Optional[str] = None):
    """Manually refresh alerts from file."""
    refresh_alerts(path)
    return {
        "status": "ok",
        "alert_count": len(alerts_store),
        "series_count": len(severity_store)
    }

@app.post("/analysis/start")
def start_analysis(history_days: int = 14, lookback_days: int = 30):
    """Start the Rust anomaly detector as a subprocess and ingest alerts in real time."""
    global _analysis_process, _analysis_thread, _analysis_status

    if _analysis_status["running"]:
        return {"status": "already_running", **_analysis_status}

    # Load and split data
    data_path = get_data_path("flattened_trends_data.json")
    if not os.path.exists(data_path):
        return {"status": "error", "detail": "flattened_trends_data.json not found"}

    with open(data_path, "r", encoding="utf-8") as f:
        records = json.load(f)
    records.sort(key=lambda r: r["timestamp"])

    # Split: oldest portion for baseline, newest history_days for live detection
    newest_ts = records[-1]["timestamp"]
    cutoff_dt = datetime.fromisoformat(newest_ts.replace("Z", "+00:00")) - timedelta(days=history_days)
    cutoff_str = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    history = [r for r in records if r["timestamp"] <= cutoff_str]
    live = [r for r in records if r["timestamp"] > cutoff_str]

    if not history or not live:
        return {"status": "error", "detail": f"Bad split: {len(history)} history, {len(live)} live"}

    # Write history to temp file
    history_fd = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(history, history_fd)
    history_fd.close()
    history_path = history_fd.name

    # Locate Rust binary
    rust_bin = get_data_path("processing/target/release/trends_analyser")
    if not os.path.exists(rust_bin):
        os.unlink(history_path)
        return {"status": "error", "detail": "Rust binary not found — run: cd processing && cargo build --release"}

    proc = subprocess.Popen(
        [rust_bin, history_path, str(lookback_days)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )
    _analysis_process = proc
    _analysis_status = {"running": True, "alerts_ingested": 0, "live_total": len(live)}

    def run():
        # Feed live data to stdin in a separate thread to avoid pipe deadlock
        def feed():
            try:
                for rec in live:
                    proc.stdin.write(json.dumps(rec, separators=(",", ":")) + "\n")
                proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass

        feeder = threading.Thread(target=feed, daemon=True)
        feeder.start()

        # Read alerts from stdout in real time
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                alert = json.loads(line)
                print(alert)
                alerts_store.append(alert)
                key = (alert.get("country"), alert.get("product"))
                existing = severity_store.get(key)
                if existing is None or alert.get("timestamp", "") > existing.get("timestamp", ""):
                    severity_store[key] = alert
                _analysis_status["alerts_ingested"] += 1
            except json.JSONDecodeError:
                continue

        proc.wait()
        _analysis_status["running"] = False
        try:
            os.unlink(history_path)
        except OSError:
            pass

    _analysis_thread = threading.Thread(target=run, daemon=True)
    _analysis_thread.start()

    print(history)

    return {"status": "started", "history_records": len(history), "live_records": len(live)}

@app.get("/analysis/status")
def analysis_status():
    """Check the status of a running analysis."""
    return _analysis_status

@app.post("/analysis/stop")
def stop_analysis():
    """Stop a running analysis."""
    global _analysis_process
    if _analysis_process and _analysis_status["running"]:
        _analysis_process.terminate()
        _analysis_status["running"] = False
        return {"status": "stopped", **_analysis_status}
    return {"status": "not_running"}

@app.get("/alerts")
def get_alerts(
    country: Optional[str] = None,
    product: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50
):
    """
    Get alerts with full details including matched social posts.
    
    Each alert includes:
    - location (country, coordinates, name)
    - content (from matched tweets)
    - timestamp and timeAgo
    - product
    - severity (EARLY/CONFIRMED) with level/score/color
    - metrics (searches, y, slope, accel, level_z, accel_z)
    - socialPosts (matched tweets with content, author, sentiment)
    """
    results = []

    alerts_path = Path(__file__).parent.parent / "processing" / "alerts.ndjson"
    with open(alerts_path) as f:
        alerts_store = json.load(f)

    # Process alerts (most recent first)
    for alert in reversed(alerts_store):
        # Apply filters
        if country and alert.get("country") != country:
            continue
        if product and alert.get("product") != product:
            continue
        if severity and alert.get("severity") != severity:
            continue
        
        alert_country = alert.get("country", "US")
        alert_product = alert.get("product", "unknown")
        country_info = get_country_info(alert_country)
        
        # Find matching social posts
        matching_tweets = find_matching_tweets(alert_product, alert_country, limit=3)
        
        # Build severity info
        sev_info = severity_to_level(alert.get("accel_z", 0), alert.get("severity", ""))
        
        result = {
            "id": f"{alert.get('timestamp')}_{alert_country}_{alert_product}".replace(" ", "_").replace(":", "-"),
            "timestamp": alert.get("timestamp"),
            "timeAgo": time_ago(alert.get("timestamp", "")),
            
            # Location info
            "location": {
                "country": alert_country,
                "countryName": country_info.get("name", alert_country),
                "lat": country_info.get("lat", 0),
                "lng": country_info.get("lng", 0),
            },
            
            # Product & severity
            "product": alert_product,
            "severity": alert.get("severity"),
            "severityLevel": sev_info["level"],
            "severityScore": sev_info["score"],
            "severityColor": sev_info["color"],
            
            # Metrics from analyzer
            "metrics": {
                "searches": alert.get("searches"),
                "y": alert.get("y"),
                "slope": alert.get("slope"),
                "accel": alert.get("accel"),
                "level_z": alert.get("level_z"),
                "accel_z": alert.get("accel_z"),
            },
            
            # Matched social content
            "socialPosts": [
                {
                    "id": tweet.get("id"),
                    "content": tweet.get("text"),
                    "originalText": tweet.get("original_text"),
                    "author": tweet.get("user_location", "Anonymous"),
                    "timestamp": tweet.get("timestamp"),
                    "sentiment": tweet.get("sentiment_label"),
                    "sentimentScore": tweet.get("sentiment_score"),
                    "keywords": tweet.get("keywords_matched", []),
                }
                for tweet in matching_tweets
            ]
        }
        
        results.append(result)
        if len(results) >= limit:
            break
    
    return {
        "count": len(results),
        "alerts": results
    }

@app.get("/alerts/geojson")
def alerts_geojson(severity: Optional[str] = None):
    """
    Get alerts as GeoJSON for map visualization.
    
    Returns FeatureCollection with:
    - Point geometry (lng, lat) - GeoJSON uses [longitude, latitude] order
    - Properties: weight, product, country, severity, alertCount, etc.
    """
    # Aggregate by country
    country_weights: Dict[str, Dict] = defaultdict(lambda: {
        "total_accel_z": 0,
        "alert_count": 0,
        "products": set(),
        "max_severity": "EARLY",
        "latest_alert": None
    })
    
    for alert in alerts_store:
        if severity and alert.get("severity") != severity:
            continue
            
        c = alert.get("country", "US")
        data = country_weights[c]
        data["total_accel_z"] += abs(alert.get("accel_z", 0))
        data["alert_count"] += 1
        data["products"].add(alert.get("product", "unknown"))
        if alert.get("severity") == "CONFIRMED":
            data["max_severity"] = "CONFIRMED"
        if data["latest_alert"] is None or alert.get("timestamp", "") > data["latest_alert"].get("timestamp", ""):
            data["latest_alert"] = alert
    
    features = []
    for country, data in country_weights.items():
        country_info = get_country_info(country)
        
        # Calculate weight (normalized 0-100)
        avg_accel_z = data["total_accel_z"] / max(1, data["alert_count"])
        weight = min(100, avg_accel_z * 10)
        
        sev_info = severity_to_level(avg_accel_z, data["max_severity"])
        
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [country_info.get("lng", 0), country_info.get("lat", 0)]
            },
            "properties": {
                "country": country,
                "countryName": country_info.get("name", country),
                "weight": round(weight, 2),
                "alertCount": data["alert_count"],
                "products": list(data["products"]),
                "maxSeverity": data["max_severity"],
                "severityLevel": sev_info["level"],
                "severityColor": sev_info["color"],
                "avgAccelZ": round(avg_accel_z, 2),
            }
        })
    
    return {
        "type": "FeatureCollection",
        "features": features
    }

@app.get("/severity")
def get_severity_feed(product: Optional[str] = None):
    """
    Live severity feed for all tracked products.
    
    Returns current severity status for each product:
    - globalScore (0-100)
    - globalLevel (NORMAL/WATCH/ELEVATED/HIGH/CRITICAL)
    - trend (↑/→/↓)
    - alertCount
    - affectedCountries
    - countries: per-country breakdown
    """
    # Build severity matrix: product -> aggregated data
    severity_matrix: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "countries": {},
        "alertCount": 0
    })
    
    for (country, prod), alert in severity_store.items():
        if product and prod != product:
            continue
        if prod not in TRACKED_PRODUCTS:
            continue
            
        sev_info = severity_to_level(alert.get("accel_z", 0), alert.get("severity", ""))
        country_info = get_country_info(country)
        
        prod_data = severity_matrix[prod]
        prod_data["countries"][country] = {
            "countryName": country_info.get("name", country),
            "severity": alert.get("severity"),
            "severityLevel": sev_info["level"],
            "severityScore": sev_info["score"],
            "severityColor": sev_info["color"],
            "accel_z": round(alert.get("accel_z", 0), 2),
            "searches": alert.get("searches"),
            "timestamp": alert.get("timestamp"),
            "timeAgo": time_ago(alert.get("timestamp", "")),
        }
        prod_data["alertCount"] += 1
    
    # Build results for all tracked products
    results = []
    for prod in TRACKED_PRODUCTS:
        if product and prod != product:
            continue
            
        data = severity_matrix.get(prod, {"countries": {}, "alertCount": 0})
        
        # Calculate global score as max of country scores
        country_scores = [
            c.get("severityScore", 0) 
            for c in data.get("countries", {}).values()
        ]
        global_score = max(country_scores) if country_scores else 0
        
        # Determine global level and color
        if global_score >= 75:
            global_level, color = "CRITICAL", "#dc2626"
        elif global_score >= 50:
            global_level, color = "HIGH", "#ea580c"
        elif global_score >= 25:
            global_level, color = "ELEVATED", "#ca8a04"
        elif global_score > 0:
            global_level, color = "WATCH", "#2563eb"
        else:
            global_level, color = "NORMAL", "#16a34a"
        
        # Determine trend based on alert count
        alert_count = data["alertCount"]
        if alert_count >= 5:
            trend = "↑↑"
        elif alert_count >= 2:
            trend = "↑"
        elif alert_count == 1:
            trend = "→"
        else:
            trend = "→"
        
        results.append({
            "product": prod,
            "globalScore": global_score,
            "globalLevel": global_level,
            "globalColor": color,
            "trend": trend,
            "alertCount": alert_count,
            "affectedCountries": len(data.get("countries", {})),
            "countries": data.get("countries", {}),
        })
    
    # Sort by global score descending
    results.sort(key=lambda x: (-x["globalScore"], x["product"]))
    
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "totalProducts": len(TRACKED_PRODUCTS),
        "productsWithAlerts": sum(1 for r in results if r["alertCount"] > 0),
        "products": results
    }

@app.get("/feed")
def get_feed(limit: int = 20, viral_only: bool = False):
    """
    Social media feed with viral/trending posts related to shortages.
    
    Returns posts with:
    - title, content, originalContent
    - viral flag
    - timestamp, timeAgo
    - location
    - sentiment, sentimentScore
    - keywords, product
    """
    feed = []
    
    for tweet in TWEETS:
        # Determine if viral
        is_viral = (
            tweet.get("keyword_tier", 3) == 1 or
            "panic" in tweet.get("text", "").lower() or
            "empty" in tweet.get("text", "").lower() or
            "shortage" in tweet.get("text", "").lower()
        )
        
        if viral_only and not is_viral:
            continue
        
        text = tweet.get("text", "")
        title = text[:60] + "..." if len(text) > 60 else text
        
        feed.append({
            "id": tweet.get("id"),
            "title": title,
            "content": text,
            "originalContent": tweet.get("original_text"),
            "viral": is_viral,
            "timestamp": tweet.get("timestamp"),
            "timeAgo": time_ago(tweet.get("timestamp", "")),
            "location": tweet.get("user_location", "Unknown"),
            "sentiment": tweet.get("sentiment_label"),
            "sentimentScore": tweet.get("sentiment_score"),
            "keywords": tweet.get("keywords_matched", []),
            "product": tweet.get("matched_product"),
            "keywordTier": tweet.get("keyword_tier"),
        })
        
        if len(feed) >= limit:
            break
    
    return {
        "count": len(feed),
        "posts": feed
    }

@app.get("/shortages")
def shortages_geojson():
    """
    Legacy endpoint - returns shortage data as GeoJSON.
    Uses real alerts if available, otherwise mock data.
    """
    # If we have real alerts, use them
    if alerts_store:
        return alerts_geojson()
    
    # Fallback to mock data
    regions = [
        {"name": "New York, USA", "coords": [-74.006, 40.7128], "country": "US"},
        {"name": "Los Angeles, USA", "coords": [-118.2437, 34.0522], "country": "US"},
        {"name": "London, UK", "coords": [-0.1278, 51.5074], "country": "GB"},
        {"name": "Tokyo, JP", "coords": [139.6917, 35.6895], "country": "JP"},
        {"name": "Sydney, AU", "coords": [151.2093, -33.8688], "country": "AU"},
        {"name": "Paris, FR", "coords": [2.3522, 48.8566], "country": "FR"},
        {"name": "Toronto, CA", "coords": [-79.3832, 43.6532], "country": "CA"},
        {"name": "Berlin, DE", "coords": [13.405, 52.52], "country": "DE"},
        {"name": "Mumbai, IN", "coords": [72.8777, 19.0760], "country": "IN"},
        {"name": "Rio de Janeiro, BR", "coords": [-43.1729, -22.9068], "country": "BR"},
    ]

    features = []
    for region in regions:
        demand = random.randint(50, 500)
        supply = random.randint(10, 400)

        if demand > supply:
            weight = round(demand / supply, 2)
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": region["coords"]
                },
                "properties": {
                    "name": region["name"],
                    "country": region["country"],
                    "demand": demand,
                    "supply": supply,
                    "weight": weight
                }
            })

    return {
        "type": "FeatureCollection",
        "features": features
    }

@app.get("/products")
def get_products():
    """Get list of all tracked products."""
    return {
        "count": len(TRACKED_PRODUCTS),
        "products": TRACKED_PRODUCTS
    }

@app.get("/countries")
def get_countries():
    """Get list of all tracked countries with coordinates."""
    countries = [
        {
            "code": code,
            "name": info["name"],
            "lat": info["lat"],
            "lng": info["lng"]
        }
        for code, info in NATION_GEOLOCATION.items()
    ]
    return {
        "count": len(countries),
        "countries": countries
    }

@app.get("/stats")
def get_stats():
    """Get current system statistics."""
    # Count alerts by severity
    severity_counts = defaultdict(int)
    for alert in alerts_store:
        severity_counts[alert.get("severity", "UNKNOWN")] += 1
    
    # Count alerts by country
    country_counts = defaultdict(int)
    for alert in alerts_store:
        country_counts[alert.get("country", "UNKNOWN")] += 1
    
    # Count alerts by product
    product_counts = defaultdict(int)
    for alert in alerts_store:
        product_counts[alert.get("product", "UNKNOWN")] += 1
    
    # Top 5 products by alert count
    top_products = sorted(product_counts.items(), key=lambda x: -x[1])[:5]
    
    # Top 5 countries by alert count
    top_countries = sorted(country_counts.items(), key=lambda x: -x[1])[:5]
    
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "alerts": {
            "total": len(alerts_store),
            "bySeverity": dict(severity_counts),
        },
        "tweets": {
            "total": len(TWEETS),
        },
        "series": {
            "total": len(severity_store),
        },
        "topProducts": [{"product": p, "count": c} for p, c in top_products],
        "topCountries": [{"country": c, "count": n} for c, n in top_countries],
    }
