from collections import defaultdict

def build_features(posts):
    buckets = defaultdict(lambda: {
        "count": 0,
        "weak_signal_sum": 0.0
    })

    for p in posts:
        key = (p["region"], p["product"])
        buckets[key]["count"] += 1
        buckets[key]["weak_signal_sum"] += p["weak_score"]

    return buckets
