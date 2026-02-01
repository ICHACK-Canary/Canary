#!/usr/bin/env python3
import json
import sys
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone


def parse_ts(s: str) -> datetime:
    # "2026-02-01T12:00:00Z" -> aware datetime UTC
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def ts_to_str(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def floor_to_hour(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


def group_to_history_json(records):
    """
    records: list of {timestamp(str), region, product, searches(float)}
    returns grouped:
      [{ region, products: [{ product, points: [{timestamp, searches}, ... newest-first]}]}]
    """
    buckets = defaultdict(lambda: defaultdict(list))
    for r in records:
        buckets[r["region"]][r["product"]].append({
            "timestamp": r["timestamp"],
            "searches": float(r["searches"]),
        })

    out = []
    for region in sorted(buckets.keys()):
        products = []
        for product in sorted(buckets[region].keys()):
            pts = buckets[region][product]
            # ensure newest-first
            pts.sort(key=lambda p: parse_ts(p["timestamp"]), reverse=True)
            products.append({"product": product, "points": pts})
        out.append({"region": region, "products": products})
    return out


def main():
    ap = argparse.ArgumentParser(
        description="From flat input sorted by decreasing timestamp: write most recent N days to history.json, then interactively emit older hours to NDJSON."
    )
    ap.add_argument("input_json", help="Path to flat input JSON (list of records), newest-first.")
    ap.add_argument("--history-days", type=int, required=True, help="Number of most recent days to put into history.json.")
    ap.add_argument("--history-out", default="history.json", help="Output path for history.json")
    ap.add_argument("--ndjson-out", default="live.ndjson", help="Output path for live NDJSON")
    args = ap.parse_args()

    with open(args.input_json, "r", encoding="utf-8") as f:
        records = json.load(f)

    if not isinstance(records, list) or not records:
        print("Input JSON must be a non-empty list of records.", file=sys.stderr)
        sys.exit(1)

    # Parse timestamps. Input is newest-first; we keep that order.
    for r in records:
        if not all(k in r for k in ("timestamp", "region", "product", "searches")):
            raise ValueError("Each record must have timestamp, region, product, searches")
        r["_dt"] = parse_ts(r["timestamp"])

    # Determine the "most recent N days" cutoff relative to the newest timestamp
    newest = records[0]["_dt"]
    history_start = newest - timedelta(days=args.history_days)

    # history = records within [history_start, newest]
    history_records = [r for r in records if r["_dt"] >= history_start]
    live_records = [r for r in records if r["_dt"] < history_start]

    if not history_records:
        print("History set is empty. Increase --history-days or check timestamps.", file=sys.stderr)
        sys.exit(1)

    # Write history.json (grouped) using the history_records
    history_payload = group_to_history_json([
        {
            "timestamp": ts_to_str(r["_dt"]),
            "region": r["region"],
            "product": r["product"],
            "searches": float(r["searches"]),
        }
        for r in history_records
    ])

    with open(args.history_out, "w", encoding="utf-8") as f:
        json.dump(history_payload, f, indent=2)

    print(f"Wrote history to: {args.history_out}")
    print(f"History window: {ts_to_str(history_start)} -> {ts_to_str(newest)}")
    if live_records:
        oldest_in_history = min(history_records, key=lambda x: x["_dt"])["_dt"]
        print(f"Next live emission starts just before: {ts_to_str(oldest_in_history)}")
    else:
        print("No remaining live records after history window (everything is in history).")
        sys.exit(0)

    print()

    # Bucket remaining (older) live records by hour (UTC), still going newest->oldest
    hour_buckets = defaultdict(list)
    for r in live_records:
        hour = floor_to_hour(r["_dt"])
        hour_buckets[hour].append(r)

    # We want to emit in decreasing time (newest hour first among the live set)
    hours_desc = sorted(hour_buckets.keys(), reverse=True)

    print(f"Prepared {len(hours_desc)} hourly buckets for replay (older than history).")
    print(f"Each Enter will append ONE hour of NDJSON to {args.ndjson_out}. Ctrl+C to stop.")
    print()

    # Truncate/create NDJSON output
    with open(args.ndjson_out, "w", encoding="utf-8") as f:
        f.write("")
    ndjson_f = open(args.ndjson_out, "a", encoding="utf-8")

    try:
        for i, hour in enumerate(hours_desc):
            input(f"[{i+1}/{len(hours_desc)}] Press Enter to emit hour starting {ts_to_str(hour)} ...")

            bucket = hour_buckets[hour]
            # stable ordering within hour
            bucket.sort(key=lambda r: (r["region"], r["product"]))

            for r in bucket:
                out_obj = {
                    "timestamp": ts_to_str(r["_dt"]),
                    "region": r["region"],
                    "product": r["product"],
                    "searches": float(r["searches"]),
                }
                line = json.dumps(out_obj, separators=(",", ":"))
                ndjson_f.write(line + "\n")
                print(line)

            ndjson_f.flush()
            print(f"Emitted {len(bucket)} records for hour {ts_to_str(hour)}\n")

        print("Replay complete.")
    finally:
        ndjson_f.close()


if __name__ == "__main__":
    main()
