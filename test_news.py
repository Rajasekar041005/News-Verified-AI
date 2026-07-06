import requests
import feedparser
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("TEST 1: NewsAPI raw request (bypassing the wrapper)")
print("=" * 60)

api_key = os.getenv("NEWS_API_KEY", "")
print("NEWS_API_KEY loaded:", bool(api_key), "| length:", len(api_key))

try:
    r = requests.get(
        "https://newsapi.org/v2/everything",
        params={
            "q": "India",
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 5,
            "apiKey": api_key,
        },
        timeout=12,
    )
    print("Status code:", r.status_code)
    print("Response body:", r.text[:500])
except Exception as e:
    print("Request raised an exception:", repr(e))

print()
print("=" * 60)
print("TEST 2: Tamil RSS feeds -- raw status + content preview")
print("=" * 60)

tamil_sources = {
    "Thanthi TV": "https://www.dailythanthi.com/rss",
    "Dinamalar": "https://www.dinamalar.com/rss.php",
    "Dinamani": "https://www.dinamani.com/rss_feed/",
    "News18 Tamil": "https://tamil.news18.com/rss",
    "Puthiya Thalaimurai": "https://www.puthiyathalaimurai.com/rss",
}

for name, url in tamil_sources.items():
    print("\n---", name, ":", url, "---")
    try:
        r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        print("Status code:", r.status_code)
        print("Content-Type:", r.headers.get("Content-Type"))
        print("First 300 chars of body:", r.text[:300].replace("\n", " "))

        feed = feedparser.parse(r.content)
        print("feedparser bozo (parse error flag):", feed.bozo)
        if feed.bozo:
            print("feedparser bozo_exception:", feed.bozo_exception)
        print("Number of entries parsed:", len(feed.entries))
    except Exception as e:
        print("Request raised an exception:", repr(e))