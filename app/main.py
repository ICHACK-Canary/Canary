from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import random

app = FastAPI()

# Enable CORS for all origins, methods, and headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # allow all headers
)

def country_to_location(country):
    nation_geolocation = {
        'US': (40.592998, -97.989633),
        'CN': (34.125123, 103.323753),
        'JP': (36.180814, 139.391852),
        'DE': (51.718119, 10.134006),
        'IN': (22.252333, 77.842872),
        'GB': (52.509086, -1.156463),
        'FR': (47.322551, 1.907086),
        'IT': (42.442869, 13.275428),
        'BR': (-10.335438, -51.068028),
        'CA': (55.279994, -97.900384),
        'KR': (36.579341, 127.956914),
        'RU': (65.871317, 107.778682),
        'AU': (-25.496731, 133.710404),
        'ES': (39.572586, -3.843935),
        'MX': (22.363872, -101.827129),
        'ID': (-1.057932, 114.677483),
        'NL': (52.133566, 5.237140),
        'SA': (-30.513815, 23.129600),
        'TR': (39.019063, 34.642999),
        'SG': (1.337386, 103.852455)
    }
    
    return nation_geolocation[country]

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/feed")
def get_feed():
    return [
            {
                'title': '10 Secrets to Boost Your Productivity',
                'viral': True,
                'content': 'Discover simple yet powerful hacks to maximize your focus and get more done in less time!',
                'timeAgo': '2 hours ago',
                'likes': '1.2K',
                'location': 'New York, USA'
            },
            {
                'title': 'The Ultimate Travel Bucket List',
                'viral': True,
                'content': 'From hidden beaches to mountain escapes, here are the destinations you must visit this year.',
                'timeAgo': '5 hours ago',
                'likes': '980',
                'location': 'Bali, Indonesia'
            },
            {
                'title': '5 Easy Recipes for Busy Weeknights',
                'viral': False,
                'content': 'Quick, delicious, and healthy meals you can make in under 30 minutes.',
                'timeAgo': '1 day ago',
                'likes': '430',
                'location': 'London, UK'
            },
            {
                'title': 'Mindfulness Tips for Everyday Life',
                'viral': True,
                'content': 'Simple exercises to reduce stress and improve focus in just 10 minutes a day.',
                'timeAgo': '3 hours ago',
                'likes': '1.1K',
                'location': 'Tokyo, Japan'
            },
            {
                'title': 'Top 7 Gadgets You Didn’t Know You Needed',
                'viral': False,
                'content': 'From smart home devices to portable tech, these gadgets will make life easier.',
                'timeAgo': '12 hours ago',
                'likes': '560',
                'location': 'San Francisco, USA'
            },
            {
                'title': 'How to Start Investing with $100',
                'viral': True,
                'content': 'Beginner-friendly tips to grow your money without taking huge risks.',
                'timeAgo': '8 hours ago',
                'likes': '1.5K',
                'location': 'Toronto, Canada'
            },
            {
                'title': '5 Movies That Will Change the Way You Think',
                'viral': False,
                'content': 'A list of thought-provoking films that are perfect for your weekend watch.',
                'timeAgo': '2 days ago',
                'likes': '320',
                'location': 'Paris, France'
            }
        ]
    
@app.get("/shortages")
def shortages_geojson():
    # Mock regions with coordinates (longitude, latitude)
    regions = [
        {"name": "New York, USA", "coords": [-74.006, 40.7128]},
        {"name": "Los Angeles, USA", "coords": [-118.2437, 34.0522]},
        {"name": "London, UK", "coords": [-0.1278, 51.5074]},
        {"name": "Tokyo, JP", "coords": [139.6917, 35.6895]},
        {"name": "Sydney, AU", "coords": [151.2093, -33.8688]},
        {"name": "Paris, FR", "coords": [2.3522, 48.8566]},
        {"name": "Toronto, CA", "coords": [-79.3832, 43.6532]},
        {"name": "Berlin, DE", "coords": [13.405, 52.52]},
        {"name": "Mumbai, IN", "coords": [72.8777, 19.0760]},
        {"name": "Rio de Janeiro, BR", "coords": [-43.1729, -22.9068]},
    ]

    features = []
    for region in regions:
        # Generate random demand and supply values
        demand = random.randint(50, 500)
        supply = random.randint(10, 400)

        # Only include regions where demand > supply
        if demand > supply:
            weight = round(demand / supply, 2)  # ratio determines "weight"
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": region["coords"]
                },
                "properties": {
                    "name": region["name"],
                    "demand": demand,
                    "supply": supply,
                    "weight": weight
                }
            })

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    return geojson