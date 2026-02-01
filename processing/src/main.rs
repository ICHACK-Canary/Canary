use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use std::env;
use std::fs::File;
use std::io::{BufReader, Write};

#[derive(Debug, Deserialize)]
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
struct RegionBlock {
    region: String,
    products: Vec<ProductSeries>,
}

#[derive(Debug, Serialize)]
struct BaselineStats {
    region: String,
    product: String,
    n: usize,
    median: f64,
    mad: f64,
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
    for v in values {
        deviations.push((v - med).abs());
    }
    median(deviations)
}

fn build_baselines(
    data: &[RegionBlock],
    lookback_days: i64,
    min_samples: usize,
) -> Vec<BaselineStats> {
    let cutoff = Utc::now() - Duration::days(lookback_days);

    // Upper bound: one baseline per (region, product)
    let estimated_series_count: usize =
        data.iter().map(|r| r.products.len()).sum();
    let mut out = Vec::with_capacity(estimated_series_count);

    for region_block in data {
        for serie
