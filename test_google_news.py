"""
Quick smoke test: verify that Google News Tamil RSS returns results.
Run from the project root:
    python test_google_news.py
"""
import sys
import io

# Force UTF-8 output so Tamil characters don't crash on Windows PowerShell
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import urllib.parse
import requests
import feedparser

query = "சிவகாசி பட்டாசு தொழிற்சாலை"  # Sivakasi fireworks factory
encoded = urllib.parse.quote(query)
url = f"https://news.google.com/rss/search?q={encoded}&hl=ta&gl=IN&ceid=IN:ta"

print("Query   :", query)
print("Fetching:", url)
print()

r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
print("Status code  :", r.status_code)
print("Content-Type :", r.headers.get("Content-Type"))

feed = feedparser.parse(r.content)
print("feedparser bozo:", feed.bozo)
if feed.bozo:
    print("bozo_exception:", feed.bozo_exception)

print("Entries found :", len(feed.entries))
print()

for entry in feed.entries[:5]:
    print("-", getattr(entry, "title", "(no title)"))
    print("  link     :", getattr(entry, "link", ""))
    print("  published:", getattr(entry, "published", ""))
    print()

if len(feed.entries) == 0:
    print("⚠  No entries returned. Check network connectivity or Google News rate-limiting.")
else:
    print(f"✅ Tamil RSS is working — {len(feed.entries)} article(s) found.")
