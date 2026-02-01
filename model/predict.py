"""
Shortage score prediction pipeline.

Fetches BlueSky social media posts, groups them into fixed-width
timeslices, extracts features per slice, and runs a pre-trained
PyTorch model to produce a shortage score for each timeslice.

Output: CSV with columns [timeslice, shortage_score].

Usage:
    python model/predict.py --query "toilet paper shortage" --model model/shortage_model.pt
"""

import sys
import os
import argparse
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import torch
import pandas as pd

# Allow imports from project root when running as a script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.BlueSky import fetch_posts, analyzer
from processing.weak_signals import weak_signal_score
from processing.concept_mapper import map_to_product

# ── Constants ────────────────────────────────────────────────────────

# The 10 product categories tracked by the system (must match config/products.yaml)
PRODUCT_CATEGORIES = [
    "pasta", "toilet_paper", "rice", "flour", "hand_sanitizer",
    "canned_goods", "bread", "milk", "eggs", "baby_formula",
]
NUM_PRODUCTS = len(PRODUCT_CATEGORIES)
# Maps product name -> index for the one-hot count vector
PRODUCT_INDEX = {p: i for i, p in enumerate(PRODUCT_CATEGORIES)}

# 7 aggregate stats + 10 product counts = 17 features per timeslice
NUM_FEATURES = 7 + NUM_PRODUCTS

# ── Helpers ──────────────────────────────────────────────────────────


def parse_timestamp(ts):
    """Convert a BlueSky timestamp string (or datetime) to a tz-aware datetime."""
    if isinstance(ts, datetime):
        return ts
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(ts, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    raise ValueError(f"Cannot parse timestamp: {ts}")


# ── Pipeline stages ─────────────────────────────────────────────────


def bucket_posts(posts, slice_hours=24):
    """
    Enrich raw posts with weak-signal and product labels,
    then group them into fixed-width time buckets.

    Returns a dict mapping bucket-start datetime -> list of enriched posts.
    """
    enriched = []
    for post in posts:
        text = post["text"]
        dt = parse_timestamp(post["created_at"])
        sentiment = post["sentiment"]              # already computed by BlueSky.fetch_posts
        weak = weak_signal_score(text)             # keyword-based weak signal score
        product = map_to_product(text)             # matched product category or None

        enriched.append({
            "timestamp": dt,
            "sentiment": sentiment,
            "weak_signal": weak,
            "product": product,
        })

    if not enriched:
        return {}

    # Sort chronologically so we can determine the time range
    enriched.sort(key=lambda x: x["timestamp"])
    t_min = enriched[0]["timestamp"]
    delta = timedelta(hours=slice_hours)

    # Assign each post to a bucket using floor division on the time offset
    buckets = defaultdict(list)
    for e in enriched:
        slot = t_min + ((e["timestamp"] - t_min) // delta) * delta
        buckets[slot].append(e)

    return dict(buckets)


def build_feature_tensor(buckets):
    """
    Convert bucketed posts into a (num_timeslices, 17) float tensor.

    Feature layout per row:
        [0]  total_posts      – raw count of posts in the timeslice
        [1]  avg_sentiment    – mean VADER compound score
        [2]  sentiment_std    – std-dev of compound scores
        [3]  negative_ratio   – fraction of posts with compound <= -0.05
        [4]  positive_ratio   – fraction of posts with compound >= 0.05
        [5]  avg_weak_signal  – mean weak-signal score
        [6]  weak_signal_sum  – sum of weak-signal scores
        [7-16] product_counts – per-category mention counts (10 values)
    """
    timeslices = sorted(buckets.keys())
    features = []

    for ts in timeslices:
        posts = buckets[ts]
        n = len(posts)

        # Empty bucket -> zero vector
        if n == 0:
            features.append(torch.zeros(NUM_FEATURES))
            continue

        sentiments = [p["sentiment"] for p in posts]
        weak_signals = [p["weak_signal"] for p in posts]

        # Aggregate sentiment stats
        avg_sent = sum(sentiments) / n
        sent_std = (sum((s - avg_sent) ** 2 for s in sentiments) / n) ** 0.5
        neg_ratio = sum(1 for s in sentiments if s <= -0.05) / n
        pos_ratio = sum(1 for s in sentiments if s >= 0.05) / n

        # Aggregate weak-signal stats
        avg_weak = sum(weak_signals) / n
        weak_sum = sum(weak_signals)

        # Count how many posts mention each product category
        product_counts = [0.0] * NUM_PRODUCTS
        for p in posts:
            if p["product"] and p["product"] in PRODUCT_INDEX:
                product_counts[PRODUCT_INDEX[p["product"]]] += 1

        vec = [n, avg_sent, sent_std, neg_ratio, pos_ratio, avg_weak, weak_sum] + product_counts
        features.append(torch.tensor(vec, dtype=torch.float32))

    # Stack into a single tensor: shape (num_timeslices, NUM_FEATURES)
    tensor = torch.stack(features)
    return timeslices, tensor


# ── Model I/O ────────────────────────────────────────────────────────


def load_model(model_path):
    """Load a TorchScript (.pt) model for CPU inference."""
    model = torch.jit.load(model_path, map_location="cpu")
    model.eval()
    return model


def predict(model, feature_tensor):
    """Run the model on the feature tensor and return a list of scores."""
    with torch.no_grad():
        scores = model(feature_tensor)
    # Squeeze to 1-D (handles both single-row and multi-row outputs)
    return scores.squeeze().tolist()


# ── Main pipeline ────────────────────────────────────────────────────


def run(query, model_path, weeks_back=10, slice_hours=24, output_path=None):
    """
    End-to-end pipeline: fetch -> bucket -> featurise -> predict -> save.

    Args:
        query:       BlueSky search query (e.g. "toilet paper shortage").
        model_path:  Path to the pre-trained .pt model file.
        weeks_back:  How many weeks of historical posts to fetch.
        slice_hours: Width of each timeslice in hours.
        output_path: Where to write the output CSV (default: data/processed/timeslice_scores.csv).
    """
    # 1. Fetch posts from BlueSky via the existing data layer
    print(f"Fetching BlueSky posts for query: '{query}'")
    posts = fetch_posts(query=query, weeks_back=weeks_back)
    print(f"Fetched {len(posts)} posts")

    if not posts:
        print("No posts found.")
        return pd.DataFrame(columns=["timeslice", "shortage_score"])

    # 2. Group posts into fixed-width timeslices
    print(f"Bucketing into {slice_hours}h timeslices...")
    buckets = bucket_posts(posts, slice_hours=slice_hours)
    print(f"Created {len(buckets)} timeslices")

    # 3. Build the feature tensor (one row per timeslice)
    timeslices, feature_tensor = build_feature_tensor(buckets)
    print(f"Feature tensor shape: {feature_tensor.shape}")

    # 4. Load model and run inference
    print(f"Loading model from {model_path}")
    model = load_model(model_path)

    print("Running inference...")
    scores = predict(model, feature_tensor)
    # Handle single-timeslice edge case (squeeze returns a scalar)
    if isinstance(scores, float):
        scores = [scores]

    # 5. Build results DataFrame and write to CSV
    results = pd.DataFrame({
        "timeslice": [ts.strftime("%Y-%m-%d %H:%M:%S") for ts in timeslices],
        "shortage_score": scores,
    })

    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "processed", "timeslice_scores.csv"
        )

    results.to_csv(output_path, index=False)
    print(f"\nResults written to {output_path}")
    print(results.to_string(index=False))
    return results


# ── CLI entrypoint ───────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Predict shortage scores from BlueSky posts")
    parser.add_argument("--query", required=True, help="Search query for BlueSky")
    parser.add_argument("--model", required=True, help="Path to the .pt model file")
    parser.add_argument("--weeks-back", type=int, default=10, help="Weeks of data to fetch (default: 10)")
    parser.add_argument("--slice-hours", type=int, default=24, help="Timeslice width in hours (default: 24)")
    parser.add_argument("--output", default=None, help="Output CSV path")
    args = parser.parse_args()

    run(
        query=args.query,
        model_path=args.model,
        weeks_back=args.weeks_back,
        slice_hours=args.slice_hours,
        output_path=args.output,
    )