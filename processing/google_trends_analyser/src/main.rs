use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use chrono::NaiveDateTime;

#[derive(Debug, Serialize, Deserialize)]
struct DemandSignal {
    #[serde(flatten)]
    metrics: HashMap<String, HashMap<String, f64>>,
}

/// Computes the Z-Score of the latest data point to detect a "Run"
fn calculate_z_score(data: &Vec<f64>) -> f64 {
    if data.len() < 2 { return 0.0; }
    let mean = data.iter().sum::<f64>() / data.len() as f64;
    let std_dev = (data.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / data.len() as f64).sqrt();
    
    if std_dev == 0.0 { 0.0 } else { (data.last().unwrap() - mean) / std_dev }
}

fn process_biome(data: &Value) {
    // 1. Analyze National/Global Trends
    if let Some(iot) = data.get("interest_over_time") {
        println!("🚀 Analyzing Time-Series for Breakouts...");
        for (keyword, series) in iot.as_object().unwrap() {
            let mut values: Vec<f64> = series.as_object().unwrap()
                .values()
                .filter_map(|v| v.as_f64())
                .collect();
            
            let z = calculate_z_score(&values);
            if z > 3.0 {
                println!("⚠️  CRITICAL SURGE: Keyword '{}' is 3SD above mean! Z-Score: {:.2}", keyword, z);
            }
        }
    }

    // 2. City-Level "Heat" Detection (Recursive)
    if let Some(cities) = data.get("cities") {
        println!("\n🏙️  Identifying Critical City Biomes...");
        for (country, city_data) in cities.as_object().unwrap() {
            for (keyword, city_scores) in city_data.as_object().unwrap() {
                if let Some(scores) = city_scores.as_object() {
                    // Find city with max search interest
                    if let Some((city, score)) = scores.iter()
                        .filter_map(|(c, v)| v.as_f64().map(|val| (c, val)))
                        .max_by(|a, b| a.1.partial_cmp(&b.1).unwrap()) 
                    {
                        if score > 80.0 {
                            println!("📍 RATIONING ALERT [{}]: High pressure in {} (Score: {})", country, city, score);
                        }
                    }
                }
            }
        }
    }
}

fn main() {
    let raw_json = std::fs::read_to_string("world_demand_biome.json")
        .expect("Unable to read biome file");
    let json_data: Value = serde_json::from_str(&raw_json)
        .expect("JSON was not well-formatted");

    // Process the hierarchical tree
    process_biome(&json_data["world_summary"]);
    
    for (continent, content) in json_data["continents"].as_object().unwrap() {
        println!("\n--- Continent: {} ---", continent);
        process_biome(content);
    }
    
    process_biome(&json_data);
}