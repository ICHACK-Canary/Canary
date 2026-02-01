import requests
import pandas as pd

url = "https://api.gdeltproject.org/api/v2/doc/doc"

params = {
    "query": "hurricane",
    "mode": "ArtList",
    "format": "json",
    "maxrecords": 250,
    "startdatetime": "20240101000000",
    "enddatetime": "20240107000000"
}

response = requests.get(url, params=params)

print(response.content)

# data = response.json()

# print(data)

# articles = data.get("articles", [])

# # df = pd.DataFrame([{
# #     "date": a["seendate"],
# #     "title": a["title"],
# #     "source": a["sourceCommonName"],
# #     "tone": a["tone"],
# #     "url": a["url"]
# # } for a in articles])

# article = articles[0]

# print(article.keys())