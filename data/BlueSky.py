from atproto import Client
from datetime import datetime, timedelta, timezone
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

analyzer = SentimentIntensityAnalyzer()

"""Pulls fresh blue-sky data for the last 10 weeks with a limit of 50 entries."""
def fetch_posts(query='London toilet paper', limit=50, weeks_back=10):
    client = Client()
    client.login('ichackwinners.bsky.social', 'Kishan26')

    since = (datetime.now(timezone.utc) - timedelta(weeks=weeks_back)).strftime('%Y-%m-%dT%H:%M:%SZ')

    params = {
        'q': query,
        'sort': 'latest',
        'limit': limit,
        'since': since,
    }

    response = client.app.bsky.feed.search_posts(params=params)

    posts = []
    for post in response.posts:
        text = post.record.text
        created_at = post.record.created_at
        sentiment = analyzer.polarity_scores(text)['compound']

        posts.append({
            'text': text,
            'created_at': created_at,
            'author': post.author.handle,
            'sentiment': sentiment,
        })

    return posts


if __name__ == '__main__':
    results = fetch_posts()
    print(f"Successfully fetched {len(results)} posts\n")

    for p in results:
        compound = p['sentiment']
        if compound >= 0.05:
            label = "😊 Positive"
        elif compound <= -0.05:
            label = "😡 Negative"
        else:
            label = "😐 Neutral"

        print(f"--- @{p['author']} at {p['created_at']}, sentiment: {label} ---")
        print(f"{p['text']}\n")