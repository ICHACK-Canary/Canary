import json
import os

def transform_shortage_data(data):
    """
    Transforms nested Google Trends JSON data into a flat list of records.
    Output Format: [{timestamp, country, product, searches}]
    Sorted by: timestamp (descending)
    """
    time_index = data.get("time_index", [])
    result_list = []

    # Iterate through each country node
    for nation in data.get("data", []):
        country = nation.get("geo")
        
        # Iterate through each product (item)
        for item in nation.get("items", []):
            product = item.get("item_name")
            
            # Initialize a list to aggregate search volumes for this product per day
            daily_searches = [0.0] * len(time_index)
            
            for group in item.get("intent_groups", []):
                for variant in group.get("variants", []):
                    vals = variant.get("vals", [])
                    
                    # Sum values element-wise corresponding to the time_index
                    for i, val in enumerate(vals):
                        if i < len(daily_searches):
                            daily_searches[i] += val
                            
            # Construct the final records for this product
            for i, timestamp in enumerate(time_index):
                if i < len(daily_searches):
                     result_list.append({
                        "timestamp": timestamp,
                        "country": country,
                        "product": product,
                        "searches": round(daily_searches[i], 2)
                    })
                    
    # Sort by timestamp (descending)
    result_list.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return result_list

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    
    input_filename = "PANIC_2020_HOURLY.json"
    output_filename = "flattened_trends_data.json"

    if os.path.exists(input_filename):
        print(f"📂 Reading from {input_filename}...")
        
        try:
            with open(input_filename, "r") as f:
                json_data = json.load(f)
            
            # Transform the data
            flat_data = transform_shortage_data(json_data)
            
            # Save to new file
            with open(output_filename, "w") as f:
                json.dump(flat_data, f, indent=2)
                
            print(f"✅ Success! Transformed {len(flat_data)} records.")
            print(f"💾 Saved to: {output_filename}")
            
            # Preview first 3 lines
            print("\n👀 Preview of first 3 records:")
            print(json.dumps(flat_data[:3], indent=2))
            
        except json.JSONDecodeError:
            print("❌ Error: The file contains invalid JSON.")
        except Exception as e:
            print(f"❌ An error occurred: {str(e)}")
    else:
        print(f"❌ Error: File '{input_filename}' not found in this directory.")