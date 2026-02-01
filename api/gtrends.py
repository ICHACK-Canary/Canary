import time
import json
import hashlib
import random
import warnings
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any
import urllib3

# --- 1. SETUP & SILENCE ---

# Hide Pandas FutureWarnings
warnings.simplefilter(action='ignore', category=FutureWarning)

try:
    from pytrends.request import TrendReq
except ImportError:
    print("❌ MISSING LIBRARY: Run 'pip install pytrends pandas'")
    exit()

# Patch urllib3 for Google SSL
if not hasattr(urllib3.util.retry.Retry, 'method_whitelist'):
    urllib3.util.retry.Retry.method_whitelist = property(
        lambda self: self.allowed_methods,
        lambda self, value: setattr(self, 'allowed_methods', value)
    )

# --- 2. CONFIGURATION ---

ALL_NATIONS = [
    "US", "CN", "JP", "DE", "IN", "GB", "FR", "IT", "BR", "CA", 
    "KR", "RU", "AU", "ES", "MX", "ID", "NL", "SA", "TR", "SG"
]

ALL_ITEMS = [
    "milk", "eggs", "bread", "butter", "cheese", "yogurt", 
    "fresh fruit", "fresh vegetables", "chicken", "beef", 
    "rice", "pasta", "flour", "sugar", "oats", "cereal", 
    "canned beans", "canned soup", "instant noodles", 
    "toilet paper", "paper towels", "tissues", "cleaning wipes", 
    "disinfectant", "laundry detergent", "dish soap", "trash bags", 
    "canned tuna", "peanut butter", "cooking oil", "salt", 
    "coffee", "tea", "baby formula", "bottled water"
]

INTENT_TEMPLATES = {
    "shortage_inquiry": [
        "is there a shortage of {item}", "{item} shortage",
        "why is {item} out of stock", "{item} hard to find",
        "stores running out of {item}"
    ],
    "urgent_availability": [
        "{item} in stock near me", "where to buy {item}",
        "{item} available near me", "{item} delivery today"
    ],
    "panic_hoarding": [
        "panic buying {item}", "people hoarding {item}",
        "why is everyone buying {item}", "empty shelves {item}"
    ]
}

# --- 3. DATA MODELS ---

@dataclass
class Metrics:
    peak: float
    avg: float
    ts: str

@dataclass
class CityTrace:
    name: str
    vals: List[float]
    metrics: Metrics

@dataclass
class IntentVariant:
    query: str
    mid: str
    vals: List[float]
    metrics: Metrics
    cities: List[CityTrace] = field(default_factory=list)

@dataclass
class IntentGroupContainer:
    group_type: str
    variants: List[IntentVariant] = field(default_factory=list)

@dataclass
class ItemContainer:
    item_name: str
    intent_groups: List[IntentGroupContainer] = field(default_factory=list)

@dataclass
class NationContainer:
    geo: str
    items: List[ItemContainer] = field(default_factory=list)

@dataclass
class MasterHierarchy:
    meta: Dict[str, Any]
    time_index: List[str]
    data: List[NationContainer] = field(default_factory=list)

# --- 4. THE 2020 HISTORICAL ENGINE ---

class HistoricalPanicScanner:
    def __init__(self):
        self.pytrends = TrendReq(hl='en-US', tz=0, retries=3, backoff_factor=3, timeout=(10, 25))
        
        # --- CONFIGURING FOR FEB-MARCH 2020 ---
        # Specific dates for the COVID panic start
        self.start_date = "2020-02-20"
        self.end_date = "2020-03-05"
        self.timeframe_str = f"{self.start_date} {self.end_date}"
        
        # Create Daily Index
        # Freq='D' (Daily) is standard for historical data > 7 days ago
        self.dt_index = pd.date_range(start=self.start_date, end=self.end_date, freq='D')
        self.str_index = [t.strftime('%Y-%m-%dT%H:%M:%SZ') for t in self.dt_index]
        self.expected_len = len(self.dt_index)

    def _generate_mid(self, text: str) -> str:
        return "mid_" + hashlib.shake_128(text.encode()).hexdigest(4)

    def _calc_metrics(self, series: pd.Series) -> Metrics:
        if series.empty or series.sum() == 0:
            return Metrics(0.0, 0.0, "")
        
        peak_idx = series.idxmax()
        ts = ""

        # Check for int/float explicitly first
        if isinstance(peak_idx, (int, float)):
            # If it's an integer, map it to our master time index
            idx_int = int(peak_idx)
            if 0 <= idx_int < len(self.str_index):
                ts = self.str_index[idx_int]
        # Then check for Timestamp object
        elif hasattr(peak_idx, "strftime"):
             ts = peak_idx.strftime('%Y-%m-%dT%H:%M:%SZ') # type: ignore
        elif isinstance(peak_idx, str):
            ts = peak_idx
        
        return Metrics(
            peak=round(float(series.max()), 1),
            avg=round(float(series.mean()), 2),
            ts=ts
        )

    def fetch_batch_2020(self, keyword_list: List[str], geo: str) -> pd.DataFrame:
        """
        Fetches daily data for Feb-Mar 2020.
        """
        attempts = 0
        success = False
        full_df = pd.DataFrame()

        while attempts < 3 and not success:
            try:
                # Requesting specific 2020 timeframe
                self.pytrends.build_payload(keyword_list, cat=0, timeframe=self.timeframe_str, geo=geo)
                df = self.pytrends.interest_over_time()
                
                if not df.empty:
                    df = df.drop(columns=['isPartial'], errors='ignore')
                    # Ensure columns exist
                    for k in keyword_list:
                        if k not in df.columns:
                            df[k] = 0.0
                    full_df = df[keyword_list]
                else:
                    # Return empty DF with correct columns if no data found
                    full_df = pd.DataFrame(columns=keyword_list)

                success = True
                # Standard sleep to be polite
                time.sleep(random.uniform(2.0, 3.5)) 
                
            except Exception as e:
                attempts += 1
                if "429" in str(e):
                    print(f"      🛑 Rate Limit. Cooling down (45s)...")
                    time.sleep(45) # 2020 data might trigger stricter checks, longer sleep
                else:
                    time.sleep(2)
        
        # Normalize if data exists
        if not full_df.empty:
            for col in full_df.columns:
                mx = full_df[col].max()
                if mx > 0:
                    full_df[col] = (full_df[col] / mx) * 100
        
        return full_df

    def run(self):
        print(f"🚀 INITIALIZING 2020 COVID PANIC SCAN")
        print(f"📅 Timeframe: {self.start_date} to {self.end_date}")
        print(f"🌍 Targets: {len(ALL_NATIONS)} Nations")
        
        dataset = MasterHierarchy(
            meta={
                "version": "COVID_2020_V1",
                "generated_at": datetime.now().isoformat(),
                "timeframe": "Feb-Mar 2020"
            },
            time_index=self.str_index
        )

        for geo in ALL_NATIONS:
            print(f"\n🌍 PROCESSING NATION: {geo}")
            nation_node = NationContainer(geo=geo)

            for item in ALL_ITEMS:
                item_node = ItemContainer(item_name=item)
                
                for group_name, phrases in INTENT_TEMPLATES.items():
                    group_node = IntentGroupContainer(group_type=group_name)
                    
                    # Batching logic
                    def chunk_list(l, n):
                        for i in range(0, len(l), n): yield l[i:i + n]
                    
                    queries = [t.format(item=item) for t in phrases]
                    
                    for batch in chunk_list(queries, 5):
                        print(f"   ⚡ Batching {len(batch)} queries for '{item}' ({group_name})...")
                        batch_df = self.fetch_batch_2020(batch, geo)
                        
                        for query in batch:
                            mid = self._generate_mid(query)
                            # Initialize with 0s matching the date index length
                            vals = [0.0] * self.expected_len
                            metrics = Metrics(0.0, 0.0, "")
                            
                            if not batch_df.empty and query in batch_df.columns:
                                raw_series = batch_df[query]
                                # Reindex to ensure alignment with master index
                                aligned = raw_series.reindex(self.dt_index, fill_value=0)
                                metrics = self._calc_metrics(aligned)
                                vals = [round(float(x), 1) for x in aligned.values]

                            variant_node = IntentVariant(query=query, mid=mid, vals=vals, metrics=metrics)
                            
                            # 2020 City Drill Down (Optional/Risky - currently skipped for speed)
                            # To enable, uncomment logic similar to V7 script

                            group_node.variants.append(variant_node)
                    item_node.intent_groups.append(group_node)
                nation_node.items.append(item_node)

            dataset.data.append(nation_node)
            
            # Incremental Save
            with open("PANIC_2020_PARTIAL.json", "w") as f:
                json.dump(asdict(dataset), f, indent=None)

        with open("PANIC_2020_FINAL.json", "w") as f:
            json.dump(asdict(dataset), f, indent=2)
        
        print("\n✅ DONE. Saved to PANIC_2020_FINAL.json")

if __name__ == "__main__":
    scanner = HistoricalPanicScanner()
    try:
        scanner.run()
    except KeyboardInterrupt:
        print("\n⚠️  Script stopped by user.")