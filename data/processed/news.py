import sys
import time
import requests
import pandas as pd
from tqdm import tqdm
from datetime import datetime

TIER1_KEYWORDS = [
    "stock up", "stocking up", "buy extra", "buying extra",
    "bulk buy", "bulk buying", "panic buy", "panic buying",
    "grabbed more", "stockpile", "stockpiling", "hoarding",
]

# Tier 2: Anticipatory concern (weaker but earlier signals)
TIER2_KEYWORDS = [
    "just in case", "before it runs out", "better get some",
    "might run out", "heard there's a shortage",
    "going to be a shortage", "while it's still available",
    "before they're gone", "getting hard to find",
]

# Systemic indicators — suggest widespread behavior
SYSTEMIC_INDICATORS = [
    "everywhere", "all stores", "all locations", "whole city",
    "every shop", "nationwide", "across the country", "multiple stores",
    "entire region", "no one can find", "everyone", "whole area",
    "everyone is", "people are",
]

# Individual indicators — suggest isolated behavior
INDIVIDUAL_INDICATORS = [
    "my store", "my local", "one shop", "this location",
    "just me", "near me only", "this branch",
]

QUERIES = TIER1_KEYWORDS + TIER2_KEYWORDS + SYSTEMIC_INDICATORS + INDIVIDUAL_INDICATORS

url = "https://api.gdeltproject.org/api/v2/doc/doc"

format_date = lambda date: "".join(date.split("-")) + "000000"

dfs = []
for query in tqdm(QUERIES):
    while True:
        params = {
            "query": f'"{query}" sourcelang:eng',
            "mode": "ArtList",
            "format": "json",
            "maxrecords": 250,
            "startdatetime": format_date("2020-02-01"),
            "enddatetime": format_date("2020-04-01"),
        }

        response = requests.get(url, params=params)
        try:
            data = response.json()
            continue
        except:
            print(response.content)
            time.sleep(15)
    
    articles = data.get("articles", [])

    df = pd.DataFrame([{
        "date": a["seendate"],
        "title": a["title"],
        "language": a["language"],
        "country": a["sourcecountry"],
        "url": a["url"]
    } for a in articles])
    
    dfs.append(df)
    time.sleep(5)

    df = pd.concat(dfs)
    df.to_csv("news_processed.csv")