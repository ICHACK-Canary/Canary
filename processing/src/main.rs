use chrono::{DateTime, Duration, NaiveDate, Utc};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, VecDeque};
use std::env;
use std::fs::File;
use std::io::{self, BufRead, BufReader};

#[derive(Debug, Clone, Deserialize)]
struct Point {
    timestamp: DateTime<Utc>,
    searches: f64,
}

#[derive(Debug, Deserialize)]
struct ProductSeries {
    product: String,
    points: Vec<Point>, // newest first
}

#[derive(Debug, Deserialize)]
struct CountryBlock {
    country: String,
    products: Vec<ProductSeries>,
}

/// Flat record format from JSON files
#[derive(Debug, Deserialize)]
struct FlatRecord {
    timestamp: DateTime<Utc>,
    country: String,
    product: String,
    searches: f64,
}

#[derive(Debug, Clone)]
struct Baseline {
    // level
    level_median: f64,
    level_mad: f64,
    // slope (Δ)
    slope_median: f64,
    slope_mad: f64,
    // accel (ΔΔ)
    accel_median: f64,
    accel_mad: f64,
}

#[derive(Debug, Deserialize)]
struct LivePoint {
    timestamp: DateTime<Utc>,
    country: String,
    product: String,
    searches: f64,
}

#[derive(Debug, Default)]
struct SeriesState {
    // Rolling window of raw points within lookback_days.
    // We'll store newest at front for easy push_front and old pop_back.
    window: VecDeque<Point>,

    // Current baseline snapshot used for detection during the day
    baseline: Option<Baseline>,

    // For "rebuild baseline only on new day"
    current_day: Option<NaiveDate>,

    // Realtime smoothing + derivatives (computed on the fly)
    y_prev: Option<f64>, // EWMA value
    slope_prev: f64,

    // Persistence counters
    early_streak: u32,
    confirmed_streak: u32,
}

#[derive(Debug, Serialize)]
struct Alert {
    timestamp: DateTime<Utc>,
    country: String,
    product: String,
    severity: String, // "EARLY" | "CONFIRMED"
    searches: f64,

    // live metrics
    y: f64,
    slope: f64,
    accel: f64,

    // normalized scores
    level_z: f64,
    accel_z: f64,
}

fn median(mut values: Vec<f64>) -> f64 {
    values.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let mid = values.len() / 2;
    if values.len() % 2 == 0 {
        (values[mid - 1] + values[mid]) / 2.0
    } else {
        values[mid]
    }
}

fn mad(values: &[f64], med: f64) -> f64 {
    let mut deviations = Vec::with_capacity(values.len());
    for &v in values {
        deviations.push((v - med).abs());
    }
    median(deviations)
}

fn robust_z(x: f64, med: f64, mad_val: f64, mad_floor: f64) -> f64 {
    let denom = mad_val.abs().max(mad_floor);
    (x - med) / denom
}

/// Rebuild baseline from the current window.
/// Window contains newest->oldest points (front newest).
fn compute_baseline_from_window(window: &VecDeque<Point>) -> Option<Baseline> {
    let n = window.len();
    if n < 3 {
        return None;
    }

    // Extract level values in *time order* doesn’t matter for median/MAD,
    // but for slope/accel we need consistent adjacency. Since window is newest->oldest,
    // we'll use that order: Δ = newer - older.
    let mut level_vals = Vec::with_capacity(n);
    for p in window.iter() {
        level_vals.push(p.searches);
    }

    // slope: n-1
    let mut slope_vals = Vec::with_capacity(n - 1);
    for i in 0..(n - 1) {
        slope_vals.push(level_vals[i] - level_vals[i + 1]);
    }

    // accel: n-2
    let mut accel_vals = Vec::with_capacity(n - 2);
    for i in 0..(n - 2) {
        accel_vals.push(slope_vals[i] - slope_vals[i + 1]);
    }

    let level_med = median(level_vals.clone());
    let level_mad = mad(&level_vals, level_med);

    let slope_med = median(slope_vals.clone());
    let slope_mad = mad(&slope_vals, slope_med);

    let accel_med = median(accel_vals.clone());
    let accel_mad = mad(&accel_vals, accel_med);

    Some(Baseline {
        level_median: level_med,
        level_mad,
        slope_median: slope_med,
        slope_mad,
        accel_median: accel_med,
        accel_mad,
    })
}

/// Initialize per-series windows and baselines from flat historical data.
/// Converts flat records into grouped series internally.
fn init_states_from_history(
    flat_records: Vec<FlatRecord>,
    lookback_days: i64,
) -> HashMap<(String, String), SeriesState> {
    let mut states: HashMap<(String, String), SeriesState> = HashMap::new();

    // Find the max timestamp in the data to use as reference point
    let max_ts = flat_records
        .iter()
        .map(|r| r.timestamp)
        .max()
        .unwrap_or_else(Utc::now);
    let cutoff = max_ts - Duration::days(lookback_days);

    // Group flat records by (country, product)
    let mut grouped: HashMap<(String, String), Vec<Point>> = HashMap::new();
    for rec in flat_records {
        let key = (rec.country, rec.product);
        grouped.entry(key).or_default().push(Point {
            timestamp: rec.timestamp,
            searches: rec.searches,
        });
    }

    // Process each group
    for ((country, product), mut points) in grouped {
        // Sort by timestamp descending (newest first)
        points.sort_by(|a, b| b.timestamp.cmp(&a.timestamp));

        // Keep only points within lookback window
        let mut window = VecDeque::with_capacity(points.len());
        let mut day: Option<NaiveDate> = None;

        for p in points {
            if p.timestamp < cutoff {
                continue; // skip old points but don't break (data might not be sorted)
            }
            if day.is_none() {
                day = Some(p.timestamp.date_naive());
            }
            window.push_back(p);
        }

        let baseline = compute_baseline_from_window(&window);

        let key = (country, product);
        states.insert(
            key,
            SeriesState {
                window,
                baseline,
                current_day: day,
                ..Default::default()
            },
        );
    }

    states
}

/// Maintain rolling window: insert newest, drop anything older than cutoff.
/// Window holds newest at front, oldest at back.
fn update_window(window: &mut VecDeque<Point>, p: Point, cutoff: DateTime<Utc>) {
    window.push_front(p);
    while let Some(back) = window.back() {
        if back.timestamp < cutoff {
            window.pop_back();
        } else {
            break;
        }
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // CLI:
    // cargo run --release -- <history.json> <lookback_days> [alpha] [mad_floor] [early_z] [confirm_z] [early_k] [confirm_k] [level_mult]
    //
    // Read live NDJSON from stdin.
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        eprintln!(
            "Usage: {} <history.json> <lookback_days> [alpha] [mad_floor] [early_z] [confirm_z] [early_k] [confirm_k] [level_mult]\n\
             Live NDJSON from stdin.",
            args[0]
        );
        std::process::exit(2);
    }

    let history_path = &args[1];
    let lookback_days: i64 = args[2].parse()?;

    let alpha: f64 = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(0.30);
    let mad_floor: f64 = args.get(4).and_then(|s| s.parse().ok()).unwrap_or(1.0);

    let early_z: f64 = args.get(5).and_then(|s| s.parse().ok()).unwrap_or(3.0);
    let confirm_z: f64 = args.get(6).and_then(|s| s.parse().ok()).unwrap_or(4.0);

    let early_k: u32 = args.get(7).and_then(|s| s.parse().ok()).unwrap_or(2);
    let confirm_k: u32 = args.get(8).and_then(|s| s.parse().ok()).unwrap_or(4);

    let level_mult: f64 = args.get(9).and_then(|s| s.parse().ok()).unwrap_or(1.10);

    // Load historical flat data and init state
    let f = File::open(history_path)?;
    let reader = BufReader::new(f);
    let history: Vec<FlatRecord> = serde_json::from_reader(reader)?;
    eprintln!("Loaded {} historical records", history.len());
    let mut states = init_states_from_history(history, lookback_days);
    eprintln!("Initialized {} series", states.len());

    // Live stream reader
    let stdin = io::stdin();
    for line_res in stdin.lock().lines() {
        let line = line_res?;
        if line.trim().is_empty() {
            continue;
        }

        let lp: LivePoint = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Skipping bad JSON line: {e} | line={line}");
                continue;
            }
        };

        let key = (lp.country.clone(), lp.product.clone());
        let st = states.entry(key.clone()).or_default();

        let ts = lp.timestamp;
        let day = ts.date_naive();
        let cutoff = ts - Duration::days(lookback_days);

        // Always maintain the rolling window (Option 1)
        update_window(
            &mut st.window,
            Point {
                timestamp: ts,
                searches: lp.searches,
            },
            cutoff,
        );

        // Rebuild baseline only when a new day is observed for this series
        let day_changed = match st.current_day {
            None => true,
            Some(d) => d != day,
        };

        if day_changed {
            st.current_day = Some(day);
            st.baseline = compute_baseline_from_window(&st.window);
            // Reset streaks on baseline refresh (optional, but keeps behavior clean)
            st.early_streak = 0;
            st.confirmed_streak = 0;
        }

        // If we don't have a baseline yet (not enough window data), skip detection
        let b = match &st.baseline {
            Some(b) => b.clone(),
            None => continue,
        };

        // EWMA smoothing
        let y = match st.y_prev {
            None => {
                st.y_prev = Some(lp.searches);
                st.slope_prev = 0.0;
                continue; // need at least 2 points for derivatives
            }
            Some(y_prev) => alpha * lp.searches + (1.0 - alpha) * y_prev,
        };

        let y_prev = st.y_prev.unwrap();
        let slope = y - y_prev;
        let accel = slope - st.slope_prev;

        // Normalize using baseline (accel-focused)
        let level_z = robust_z(y, b.level_median, b.level_mad, mad_floor);
        let accel_z = robust_z(accel, b.accel_median, b.accel_mad, mad_floor);

        // Guardrails
        let level_ok = y >= b.level_median * level_mult;
        let slope_ok = slope > 0.0;

        let early_ok = level_ok && slope_ok && accel_z >= early_z;
        let confirm_ok = level_ok && slope_ok && accel_z >= confirm_z;

        if early_ok {
            st.early_streak += 1;
        } else {
            st.early_streak = 0;
        }

        if confirm_ok {
            st.confirmed_streak += 1;
        } else {
            st.confirmed_streak = 0;
        }

        // Emit alerts (NDJSON)
        if st.confirmed_streak >= confirm_k {
            let alert = Alert {
                timestamp: ts,
                country: lp.country.clone(),
                product: lp.product.clone(),
                severity: "CONFIRMED".to_string(),
                searches: lp.searches,
                y,
                slope,
                accel,
                level_z,
                accel_z,
            };
            println!("{}", serde_json::to_string(&alert)?);
            st.confirmed_streak = 0;
            st.early_streak = 0;
        } else if st.early_streak >= early_k {
            let alert = Alert {
                timestamp: ts,
                country: lp.country.clone(),
                product: lp.product.clone(),
                severity: "EARLY".to_string(),
                searches: lp.searches,
                y,
                slope,
                accel,
                level_z,
                accel_z,
            };
            println!("{}", serde_json::to_string(&alert)?);
            st.early_streak = 0;
        }

        // Update streaming state
        st.y_prev = Some(y);
        st.slope_prev = slope;
    }

    Ok(())
}
