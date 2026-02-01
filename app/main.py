from fastapi import FastAPI

app = FastAPI()

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
    return {'posts':[
        'We are running out of potatoes',
        'My day has been going well',
        'Hello Nishant :)',
        
    ]}
    
@app.get("/shortages")
def get_shortages():
    return {'shortages': [
        {'name': 'potatoes', 'weight': 0.8, 'geolocation': country_to_location("US")},
        {'name': 'bacon', 'weight': 0.2, 'geolocation': country_to_location("GB")}
    ]}