import json
import random
import numpy as np
from datetime import datetime, timedelta

# --- 1. CONFIGURATION (HISTORICAL) ---

START_DATE = datetime(2020, 2, 1)
END_DATE = datetime(2020, 3, 31)
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
        "name": "🚨 Singapore 'DORSCON Orange'", 
        "start": "2020-02-07", "end": "2020-02-14",
        "regions": ["Asia_East", "Asia_South"],
        "items": ["rice", "instant noodles", "toilet paper", "canned tuna"],
        "impact": 4.0, 
        "description": "First major panic buying wave outside China."
    },
    {
        "name": "🦠 Lombardy Lockdown Effect", 
        "start": "2020-02-23", "end": "2020-03-01",
        "regions": ["Europe"],
        "items": ["pasta", "canned soup", "disinfectant", "hand sanitizer"],
        "impact": 2.5, 
        "description": "Panic spreads to Europe as Italy locks down towns."
    },
    {
        "name": "🧻 The Great Toilet Paper Crisis", 
        "start": "2020-03-01", "end": "2020-03-20",
        "regions": ["Oceania", "NA_West", "NA_East", "NA_North", "Europe"],
        "items": ["toilet paper", "paper towels", "tissues"],
        "impact": 5.0,
        "supply_shock": True, 
        "description": "Global psychological contagion event."
    },
    {
        "name": "🇺🇸 National Emergency Declaration", 
        "start": "2020-03-13", "end": "2020-03-17",
        "regions": ["NA_East", "NA_West", "NA_North"],
        "items": ["milk", "eggs", "bread", "beef", "chicken"],
        "impact": 3.0, 
        "description": "The weekend everyone cleared the shelves."
    },
    {
        "name": "🔒 Global Lockdown Era", 
        "start": "2020-03-16", "end": "2020-03-31",
        "regions": ["NA_East", "NA_West", "NA_North", "Europe", "LATAM", "Asia_South"],
        "items": ["flour", "yeast", "canned beans", "frozen food"],
        "impact": 1.5, 
        "supply_shock": True, 
        "description": "Supply chains break down; hoarding normalization."
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
    print(f"🚀 INITIALIZING COVID-19 (2020) SIMULATION")
    print(f"📅 Timeframe: {START_DATE.date()} to {END_DATE.date()}")
    print(f"🌍 {len(CITIES)} Cities | 📦 {len(ITEMS)} Items | ⏳ {TOTAL_HOURS} Hours\n")

    full_dataset = []

    for city_name, city_info in CITIES.items():
        print(f"   Processing {city_name}...")
        region = city_info['region']
        base_curve = generate_diurnal_curve(TOTAL_HOURS, city_info['timezone'])
        
        for item in ITEMS:
            avg_vol = random.randint(15, 60) 
            demand_series = base_curve * avg_vol
            
            restock_blocked_intervals = []
            
            for event in EVENTS:
                if region in event['regions']:
                    is_target_item = item in event['items']
                    
                    if is_target_item:
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
            current_inv = max_capacity * 0.9 
            
            for t in range(TOTAL_HOURS):
                local_hour = (t + city_info['timezone']) % 24
                days_passed = t // 24
                
                is_restock_time = (local_hour == 4) and (days_passed % 3 == 0)
                restock_success = random.random() > 0.2 
                
                is_blocked = False
                for start, end in restock_blocked_intervals:
                    if start <= t <= end:
                        is_blocked = True
                        break
                
                if is_restock_time and not is_blocked and restock_success:
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
                    sent = 0.8 + random.uniform(-0.1, 0.1) 
                elif inv_health > 0.05:
                    sent = 0.5 + (inv_health * 0.5)
                else:
                    sent = 0.05 
                
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
            "version": "2020_HISTORICAL_V1_FIXED",
            "generated_at": datetime.now().isoformat(),
            "time_index": time_index,
            "events_logged": [e['name'] for e in EVENTS]
        },
        "inventory_data": full_dataset
    }

    filename = "covid_panic_2020.json"
    print(f"\n💾 Saving to {filename}...")
    
    with open(filename, "w") as f:
        json.dump(final_output, f, default=str)

    print("✅ DONE. Historical Data Generated.")

if __name__ == "__main__":
    generate_simulation()