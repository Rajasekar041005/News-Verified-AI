import urllib.parse
import requests
import feedparser

query = "சிவகாசி பட்டாசு தொழிற்சாலை"  # test with a Tamil-language query
encoded = urllib.parse.quote(query)
url = f"https://news.google.com/rss/search?q={encoded}&hl=ta&gl=IN&ceid=IN:ta"

print("Fetching:", url)

r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
print("Status code:", r.status_code)
print("Content-Type:", r.headers.get("Content-Type"))

feed = feedparser.parse(r.content)
print("feedparser bozo:", feed.bozo)
if feed.bozo:
    print("bozo_exception:", feed.bozo_exception)

print("Entries found:", len(feed.entries))
print()

for entry in feed.entries[:5]:
    print("-", getattr(entry, "title", "(no title)"))
    print("  link:", getattr(entry, "link", ""))
    print("  published:", getattr(entry, "published", ""))
    print()
import urllib.parse
import requests
import feedparser

query = "சிவகாசி பட்டாசு தொழிற்சாலை"  # test with a Tamil-language query
encoded = urllib.parse.quote(query)
url = f"https://news.google.com/rss/search?q={encoded}&hl=ta&gl=IN&ceid=IN:ta"

print("Fetching:", url)

r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
print("Status code:", r.status_code)
print("Content-Type:", r.headers.get("Content-Type"))

feed = feedparser.parse(r.content)
print("feedparser bozo:", feed.bozo)
if feed.bozo:
    print("bozo_exception:", feed.bozo_exception)

print("Entries found:", len(feed.entries))
print()

for entry in feed.entries[:5]:
    print("-", getattr(entry, "title", "(no title)"))
    print("  link:", getattr(entry, "link", ""))
    print("  published:", getattr(entry, "published", ""))
    print()
