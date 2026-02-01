import json
import random
import numpy as np
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---

START_DATE = datetime(2026, 1, 1)
END_DATE = datetime(2026, 2, 28)
# Calculate total hours safely
TOTAL_HOURS = int((END_DATE - START_DATE).total_seconds() / 3600) + 24

CITIES = {
    "New York": {"region": "NA_East", "timezone": -5},
    "Los Angeles": {"region": "NA_West", "timezone": -8},
    "Toronto": {"region": "NA_North", "timezone": -5},
    "Mexico City": {"region": "LATAM", "timezone": -6},
    "Sao Paulo": {"region": "LATAM", "timezone": -3},
    "London": {"region": "Europe", "timezone": 0},
    "Berlin": {"region": "Europe", "timezone": 1},
    "Paris": {"region": "Europe", "timezone": 1},
    "Cairo": {"region": "MENA", "timezone": 2},
    "Dubai": {"region": "MENA", "timezone": 4},
    "Mumbai": {"region": "Asia_South", "timezone": 5.5},
    "Singapore": {"region": "Asia_East", "timezone": 8},
    "Tokyo": {"region": "Asia_East", "timezone": 9},
    "Seoul": {"region": "Asia_East", "timezone": 9},
    "Sydney": {"region": "Oceania", "timezone": 11}
}

ITEMS = [
    "milk", "eggs", "bread", "butter", "cheese", "yogurt", 
    "fresh fruit", "fresh vegetables", "chicken", "beef", 
    "rice", "pasta", "flour", "sugar", "oats", "cereal", 
    "canned beans", "canned soup", "instant noodles", 
    "toilet paper", "paper towels", "tissues", "cleaning wipes", 
    "disinfectant", "laundry detergent", "dish soap", "trash bags", 
    "canned tuna", "peanut butter", "cooking oil", "salt", 
    "coffee", "tea", "baby formula", "bottled water"
]

EVENTS = [
    {
        "name": "❄️ Winter Storm 'Atlas'", 
        "start": "2026-01-20", "end": "2026-01-24",
        "regions": ["NA_East", "NA_North", "Europe"],
        "items": ["milk", "bread", "eggs", "toilet paper", "bottled water"],
        "impact": 3.5, 
        "description": "Blizzard paralysis causing panic buying."
    },
    {
        "name": "🏈 Super Bowl LX", 
        "start": "2026-02-06", "end": "2026-02-08",
        "regions": ["NA_East", "NA_West", "NA_North"],
        "items": ["chicken", "beef", "cheese", "chips", "soda"], 
        "impact": 2.0,
        "description": "Party food surge."
    },
    {
        "name": "🧧 Lunar New Year", 
        "start": "2026-02-14", "end": "2026-02-20",
        "regions": ["Asia_East", "Asia_South"],
        "items": ["rice", "fresh fruit", "chicken", "beef", "cooking oil"],
        "impact": 1.8,
        "description": "Holiday feasting and gifting."
    },
    {
        "name": "📉 Supply Chain Glitch (Port Strike)",
        "start": "2026-02-01", "end": "2026-02-15",
        "regions": ["Oceania", "LATAM"],
        "items": ["baby formula", "canned tuna", "coffee"],
        "impact": 1.2, 
        "supply_shock": True, 
        "description": "Import delays causing shortages."
    }
]

# --- HELPER FUNCTIONS ---

def get_hour_index(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    delta = dt - START_DATE
    return int(delta.total_seconds() / 3600)

def generate_diurnal_curve(length, timezone_offset):
    x = np.arange(length)
    peak_utc = (18 - timezone_offset) % 24
    phase_shift = (peak_utc / 24.0) * 2 * np.pi
    
    daily = -np.cos((x / 24.0) * 2 * np.pi - phase_shift)
    daily = (daily + 1) / 2
    daily = daily ** 4 
    
    noise = np.random.normal(0, 0.05, length)
    return np.clip(daily + noise, 0, None)

# --- GENERATOR ---

def generate_simulation():
    print(f"🚀 INITIALIZING 2026 GLOBAL SUPPLY SIMULATION")
    print(f"🌍 {len(CITIES)} Cities | 📦 {len(ITEMS)} Items | ⏳ {TOTAL_HOURS} Hours\n")

    full_dataset = []

    for city_name, city_info in CITIES.items():
        print(f"   Processing {city_name}...")
        region = city_info['region']
        base_curve = generate_diurnal_curve(TOTAL_HOURS, city_info['timezone'])
        
        for item in ITEMS:
            avg_vol = random.randint(10, 50)
            demand_series = base_curve * avg_vol
            
            restock_blocked_intervals = []
            
            for event in EVENTS:
                if region in event['regions']:
                    if item in event['items']:
                        start_idx = max(0, get_hour_index(event['start']))
                        end_idx = min(TOTAL_HOURS, get_hour_index(event['end']) + 24)
                        
                        demand_series[start_idx:end_idx] *= event['impact']
                        
                        if event.get('supply_shock'):
                            restock_blocked_intervals.append((start_idx, end_idx))

            demand_series = np.round(demand_series).astype(int)

            inventory_series = []
            sales_series = []
            sentiment_series = []
            
            max_capacity = avg_vol * 24 * 3 
            current_inv = max_capacity * 0.8 
            
            for t in range(TOTAL_HOURS):
                local_hour = (t + city_info['timezone']) % 24
                days_passed = t // 24
                
                is_restock_time = (local_hour == 4) and (days_passed % 3 == 0)
                
                is_blocked = False
                for start, end in restock_blocked_intervals:
                    if start <= t <= end:
                        is_blocked = True
                        break
                
                if is_restock_time and not is_blocked:
                    current_inv = max_capacity
                
                wanted = demand_series[t]
                
                if current_inv >= wanted:
                    sold = wanted
                    current_inv -= wanted
                else:
                    sold = current_inv 
                    current_inv = 0    
                
                inv_health = current_inv / max_capacity
                
                if inv_health > 0.4:
                    sent = 0.9 + random.uniform(-0.1, 0.1)
                elif inv_health > 0.1:
                    sent = 0.6 + (inv_health * 0.5)
                else:
                    if sold == 0 and wanted > 10:
                        sent = 0.1 
                    else:
                        sent = 0.3 + random.uniform(-0.1, 0.1)

                sent = max(0.05, min(1.0, sent))
                
                # CRITICAL FIX: Cast numpy types to Python native types
                inventory_series.append(int(current_inv))
                sales_series.append(int(sold))
                sentiment_series.append(float(round(sent, 2)))

            full_dataset.append({
                "city": city_name,
                "region": region,
                "item": item,
                "data": {
                    "sales": sales_series,
                    "inventory": inventory_series,
                    "sentiment": sentiment_series
                }
            })

    time_index = [(START_DATE + timedelta(hours=t)).strftime("%Y-%m-%dT%H:%M:%SZ") for t in range(TOTAL_HOURS)]

    final_output = {
        "meta": {
            "version": "2026_SIM_V2_FIXED",
            "generated_at": datetime.now().isoformat(),
            "time_index": time_index,
            "events_logged": [e['name'] for e in EVENTS]
        },
        "inventory_data": full_dataset
    }

    filename = "global_supermarket_2026.json"
    print(f"\n💾 Saving to {filename}...")
    
    # Safe dump with default string conversion just in case
    with open(filename, "w") as f:
        json.dump(final_output, f, default=str)

    print("✅ DONE. Simulation Complete.")

if __name__ == "__main__":
    generate_simulation()