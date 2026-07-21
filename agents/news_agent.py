import concurrent.futures
import logging
import os
import re
import urllib.parse
from typing import Dict, List, Optional

import feedparser
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("news_agent")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

_STOPWORDS = {
    "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "with",
    "of", "is", "are", "was", "were", "said", "that", "this", "from", "by",
    "as", "if", "would", "be", "open", "holding", "such", "according",
    "meeting", "during",
}

# Small curated list of very common Tamil function/reporting words.
_TAMIL_STOPWORDS = {
    "அது", "இது", "என்று", "மற்றும்", "ஆனால்", "இந்த", "அந்த", "ஒரு",
    "என", "கூறினார்", "தெரிவித்தார்", "உள்ளது", "உள்ளன", "இருந்து",
    "என்பது", "என்ன", "போன்ற", "மேலும்", "தான்", "தொடர்பாக", "பற்றி",
    "சில", "எந்த", "அவர்", "அவர்கள்", "இருக்கும்", "வேண்டும்", "செய்ய",
    "கொண்டு", "தெரிவிக்கப்பட்டுள்ளது", "என்பதை", "இருந்த", "நிலையில்",
    "என்றும்", "வர", "பட",
}

# Rotating User-Agent strings to reduce rate-limiting from Google News RSS.
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

_ua_index = 0

# Source logo / favicon template for known Tamil outlets.
# When an article has no image, the frontend can use these.
_SOURCE_LOGOS: Dict[str, str] = {
    "Dinamalar":            "https://www.dinamalar.com/images/dinamalar-logo.png",
    "Dinamani":             "https://www.dinamani.com/images/logo.png",
    "Daily Thanthi":        "https://www.dailythanthi.com/Content/images/logo.png",
    "Polimer News":         "https://yt3.ggpht.com/9fI7KtnXKXtl9HKXp0k7tJ7gfWVX1A-bYi-g8Kxb4A=s176",
    "Puthiya Thalaimurai":  "https://yt3.ggpht.com/ytc/AIdro_lqF7vvGRRiPfsMGqf2yv=s176",
    "Thanthi TV":           "https://yt3.ggpht.com/ytc/AIdro_k2gvyGLRQl3bS=s176",
    "News18 Tamil":         "https://yt3.ggpht.com/ytc/AIdro_lXuK=s176",
    "Sun News":             "https://yt3.ggpht.com/ytc/AIdro_koM=s176",
    "BBC Tamil":            "https://ichef.bbci.co.uk/images/ic/1200x675/p07c7f6k.jpg",
    "The Hindu":            "https://www.thehindu.com/theme/images/th-online/thehindu-logo.png",
    "India Today":          "https://akm-img-a-in.tosshub.com/indiatoday/images/logo/logo_india_today.png",
    "Google News (Tamil)":  "https://www.google.com/images/branding/googleg/1x/googleg_standard_color_128dp.png",
}


def _next_user_agent() -> str:
    global _ua_index
    ua = _USER_AGENTS[_ua_index % len(_USER_AGENTS)]
    _ua_index += 1
    return ua


def _fetch_og_image(url: str, timeout: float = 3.0) -> str:
    """
    Scrape the og:image or twitter:image meta tag from an article page.
    Returns the image URL string, or empty string on failure.
    Short timeout (3s) so it never blocks the pipeline for long.
    """
    if not url:
        return ""
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={
                "User-Agent": _next_user_agent(),
                "Accept": "text/html,application/xhtml+xml",
            },
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return ""
        html = resp.text
        # Try og:image first
        m = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.IGNORECASE,
        )
        if not m:
            m = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                html, re.IGNORECASE,
            )
        if not m:
            # Fallback: twitter:image
            m = re.search(
                r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
                html, re.IGNORECASE,
            )
        if m:
            img = m.group(1).strip()
            # Make absolute if relative
            if img.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(url)
                img = f"{parsed.scheme}://{parsed.netloc}{img}"
            return img
    except Exception:
        pass
    return ""


def _enrich_images_parallel(articles: List[Dict], max_articles: int = 10) -> None:
    """
    For up to `max_articles` articles that have no image, fetch og:image
    in parallel using a thread pool. Mutates `articles` in-place.
    This avoids sequential scraping (25×3s = 75s worst case).
    """
    candidates = [
        art for art in articles
        if not art.get("image") and art.get("url")
    ][:max_articles]

    if not candidates:
        return

    def _fetch(art: Dict) -> None:
        img = _fetch_og_image(art["url"])
        if img:
            art["image"] = img

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_fetch, art) for art in candidates]
        # Wait at most 12 seconds total for all parallel fetches
        concurrent.futures.wait(futures, timeout=12)



def _source_image(source: str, url: str) -> str:
    """Return a known logo for recognised sources, else empty string.
    Favicons are too small to use as article images in the gallery."""
    for key, logo in _SOURCE_LOGOS.items():
        if key.lower() in source.lower():
            return logo
    return ""


class NewsAgent:
    def __init__(self):
        self.newsapi_key = os.getenv("NEWS_API_KEY", "")
        self.gnews_key = os.getenv("GNEWS_API_KEY", "")
        self.newsdata_key = os.getenv("NEWSDATA_API_KEY", "")
        self.timeout = float(os.getenv("NEWS_TIMEOUT_SECONDS", "12"))

        # Google News RSS search endpoint
        self.google_news_tamil_url = (
            "https://news.google.com/rss/search?q={query}&hl=ta&gl=IN&ceid=IN:ta"
        )
        self.google_news_english_url = (
            "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        )

        # Major Tamil news YouTube channel IDs
        self._tamil_yt_channels = {
            "Polimer News":        "UCkN9PNBrsSQ-o80KBFU3cKA",
            "Puthiya Thalaimurai": "UCFqK7-4E_g3DGXF7EZ4t7yQ",
            "Thanthi TV":         "UCOq0l-k1X7fFGwHMWVYv0DA",
            "News18 Tamil":       "UCXjMRrHfKW7RdQnkAkQDOyg",
            "Sun News":           "UCjvv7d1MHkSs-GqTL8SqPiA",
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_news(
        self,
        query: str,
        language: str = "en",
        english_query: Optional[str] = None,
    ) -> List[Dict]:
        """
        query: the claim text in its ORIGINAL language.
        english_query: the claim translated to English — used for NewsAPI
                       and English-language Google News.
        """
        articles: List[Dict] = []

        newsapi_query = english_query or query
        keyword_query = self._extract_keywords(newsapi_query)

        # --- English sources ---
        if self.newsapi_key:
            articles.extend(self._fetch_newsapi(keyword_query, "en"))

        # Always fetch English Google News RSS (catches Indian English press)
        english_kw = self._extract_keywords(english_query or query)
        articles.extend(self._fetch_feed(
            self.google_news_english_url.format(
                query=urllib.parse.quote(english_kw)
            ),
            default_lang="en",
        ))

        # --- Tamil sources ---
        # Primary: Google News Tamil RSS
        articles.extend(self._fetch_tamil_rss([query]))

        # Secondary: GNews API (free tier supports lang=ta, country=IN)
        if self.gnews_key:
            ta_kw = self._extract_tamil_keywords(query) if language == "ta" else keyword_query
            articles.extend(self._fetch_gnews(ta_kw, language))

        # Tertiary: NewsData.io (free tier, supports language=tamil)
        if self.newsdata_key:
            ta_kw = self._extract_tamil_keywords(query) if language == "ta" else keyword_query
            articles.extend(self._fetch_newsdata(ta_kw, language))

        # Quaternary: Wikipedia summary (always available, no key needed)
        articles.extend(self._fetch_wikipedia(english_query or keyword_query))

        # YouTube Tamil news channels — always included for Tamil content,
        # with improved matching that doesn't require English keywords in Tamil titles
        if language == "ta":
            articles.extend(self._fetch_youtube_tamil_latest())
        else:
            # For English queries, fetch YouTube with keyword matching
            articles.extend(self._fetch_youtube_english(keyword_query))

        # Ensure every article has a known-source logo fallback
        for art in articles:
            if not art.get("image"):
                art["image"] = _source_image(art.get("source", ""), art.get("url", ""))

        # --- Deduplicate ---
        deduped: List[Dict] = []
        seen: set = set()

        for article in articles:
            fingerprint = (
                article.get("title", "").strip().lower(),
                article.get("url", "").strip().lower(),
            )
            if fingerprint in seen or not any(fingerprint):
                continue
            seen.add(fingerprint)
            deduped.append(article)

        deduped = deduped[:30]

        # --- Parallel og:image enrichment (only for articles still missing images) ---
        _enrich_images_parallel(deduped, max_articles=5)

        return deduped

    def fetch_live_news(self, language: str = "en", max_items: int = 20) -> List[Dict]:
        """
        Fetch the latest top news without any query — for the live ticker
        and trending panel. No verification is applied.
        """
        articles: List[Dict] = []

        if language == "ta":
            # Top Tamil news
            feed_url = "https://news.google.com/rss?hl=ta&gl=IN&ceid=IN:ta"
            articles.extend(self._fetch_feed(feed_url, default_lang="ta"))
            # YouTube latest (no keyword filter)
            articles.extend(self._fetch_youtube_tamil_latest(max_per_channel=2))
        else:
            # Top Indian English news
            feed_url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
            articles.extend(self._fetch_feed(feed_url, default_lang="en"))

        for art in articles:
            if not art.get("image"):
                art["image"] = _source_image(art.get("source", ""), art.get("url", ""))

        return articles[:max_items]

    def fetch_trending_topics(self) -> List[str]:
        """
        Extract trending topic keywords from the top Tamil + English Google News feeds.
        """
        topics: List[str] = []

        for feed_url in [
            "https://news.google.com/rss?hl=ta&gl=IN&ceid=IN:ta",
            "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en",
        ]:
            try:
                response = requests.get(
                    feed_url,
                    timeout=self.timeout,
                    headers={"User-Agent": _next_user_agent()},
                )
                if response.status_code == 200:
                    feed = feedparser.parse(response.content)
                    for entry in feed.entries[:10]:
                        title = getattr(entry, "title", "")
                        if title and " - " in title:
                            title = title.rpartition(" - ")[0].strip()
                        if title and len(title) < 80:
                            topics.append(title)
            except Exception:
                pass

        return topics[:15]

    # ------------------------------------------------------------------
    # Keyword extraction helpers
    # ------------------------------------------------------------------

    def _extract_keywords(self, text: str, max_terms: int = 6) -> str:
        if not text:
            return text

        words = re.findall(r"[A-Za-z][A-Za-z'\-]*", text)

        capitalized = [w for w in words if w[0].isupper() and w.lower() not in _STOPWORDS]
        others = [w for w in words if w.lower() not in _STOPWORDS and w not in capitalized]

        ordered: List[str] = []
        seen: set = set()
        for w in capitalized + others:
            lw = w.lower()
            if lw in seen:
                continue
            seen.add(lw)
            ordered.append(w)
            if len(ordered) >= max_terms:
                break

        return " ".join(ordered) if ordered else text

    def _extract_tamil_keywords(self, text: str, max_terms: int = 6) -> str:
        if not text:
            return text

        tokens = re.findall(r"[\u0B80-\u0BFF]+", text)
        candidates = [t for t in tokens if len(t) >= 3 and t not in _TAMIL_STOPWORDS]
        if not candidates:
            candidates = [t for t in tokens if len(t) >= 2]
        if not candidates:
            return text

        seen: set = set()
        ordered: List[str] = []
        for token in sorted(candidates, key=len, reverse=True):
            if token in seen:
                continue
            seen.add(token)
            ordered.append(token)
            if len(ordered) >= max_terms:
                break

        return " ".join(ordered) if ordered else text

    # ------------------------------------------------------------------
    # NewsAPI (English only)
    # ------------------------------------------------------------------

    def _fetch_newsapi(self, query: str, language: str) -> List[Dict]:
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 10,
            "apiKey": self.newsapi_key,
        }
        try:
            response = requests.get(
                "https://newsapi.org/v2/everything",
                params=params,
                timeout=self.timeout,
                headers={"User-Agent": _next_user_agent()},
            )
        except Exception:
            logger.exception("NewsAPI request failed for query='%s'", query)
            return []

        if response.status_code != 200:
            logger.warning(
                "NewsAPI returned status %s for query='%s': %s",
                response.status_code, query, response.text[:300]
            )
            return []

        data = response.json()
        articles = []

        for article in data.get("articles", []):
            articles.append({
                "title":    article.get("title", ""),
                "content":  article.get("description", ""),
                "url":      article.get("url", ""),
                "image":    article.get("urlToImage", ""),
                "source":   article.get("source", {}).get("name", "NewsAPI"),
                "date":     article.get("publishedAt", ""),
                "language": language,
                "provider": "newsapi",
            })

        return articles

    # ------------------------------------------------------------------
    # GNews API
    # ------------------------------------------------------------------

    def _fetch_gnews(self, query: str, language: str) -> List[Dict]:
        lang_code = "ta" if language == "ta" else "en"
        params = {
            "q":       query,
            "lang":    lang_code,
            "country": "in",
            "max":     10,
            "apikey":  self.gnews_key,
        }
        try:
            response = requests.get(
                "https://gnews.io/api/v4/search",
                params=params,
                timeout=self.timeout,
                headers={"User-Agent": _next_user_agent()},
            )
        except Exception:
            logger.exception("GNews request failed for query='%s'", query)
            return []

        if response.status_code != 200:
            logger.warning(
                "GNews returned status %s for query='%s': %s",
                response.status_code, query, response.text[:300]
            )
            return []

        data = response.json()
        articles = []

        for article in data.get("articles", []):
            articles.append({
                "title":    article.get("title", ""),
                "content":  article.get("description", ""),
                "url":      article.get("url", ""),
                "image":    article.get("image", ""),
                "source":   article.get("source", {}).get("name", "GNews"),
                "date":     article.get("publishedAt", ""),
                "language": lang_code,
                "provider": "gnews",
            })

        return articles

    # ------------------------------------------------------------------
    # NewsData.io API
    # ------------------------------------------------------------------

    def _fetch_newsdata(self, query: str, language: str) -> List[Dict]:
        lang_code = "tamil" if language == "ta" else "english"
        params = {
            "q":        query,
            "country":  "in",
            "language": lang_code,
            "apikey":   self.newsdata_key,
        }
        try:
            response = requests.get(
                "https://newsdata.io/api/1/news",
                params=params,
                timeout=self.timeout,
                headers={"User-Agent": _next_user_agent()},
            )
        except Exception:
            logger.exception("NewsData request failed for query='%s'", query)
            return []

        if response.status_code != 200:
            logger.warning(
                "NewsData returned status %s for query='%s': %s",
                response.status_code, query, response.text[:300]
            )
            return []

        data = response.json()
        articles = []

        for article in (data.get("results") or []):
            articles.append({
                "title":    article.get("title", ""),
                "content":  article.get("description", "") or article.get("content", ""),
                "url":      article.get("link", ""),
                "image":    article.get("image_url", ""),
                "source":   article.get("source_id", "NewsData"),
                "date":     article.get("pubDate", ""),
                "language": "ta" if language == "ta" else "en",
                "provider": "newsdata",
            })

        return articles

    # ------------------------------------------------------------------
    # Wikipedia — free, always-available knowledge source
    # ------------------------------------------------------------------

    def _fetch_wikipedia(self, query: str) -> List[Dict]:
        """
        Fetches a Wikipedia summary for the query. Zero API key required.
        Returns 1-2 articles with the summary as content so the RAG agent
        can use them as evidence.
        """
        if not query or len(query.strip()) < 3:
            return []

        # Use first 5 keywords to avoid overly specific queries
        search_term = " ".join(query.split()[:5])

        try:
            # Wikipedia OpenSearch to find article titles
            search_resp = requests.get(
                "https://en.wikipedia.org/api/rest_v1/page/summary/" +
                urllib.parse.quote(search_term.replace(" ", "_")),
                timeout=8,
                headers={"User-Agent": "NewsVerifiedAI/1.0 (fact-checking app)"},
            )
            if search_resp.status_code == 200:
                data = search_resp.json()
                title = data.get("title", "")
                extract = data.get("extract", "")
                page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
                thumbnail = (data.get("thumbnail") or {}).get("source", "")

                if extract and len(extract) > 50:
                    return [{
                        "title":    f"Wikipedia: {title}",
                        "content":  extract[:800],
                        "url":      page_url,
                        "image":    thumbnail,
                        "source":   "Wikipedia",
                        "date":     "",
                        "language": "en",
                        "provider": "wikipedia",
                    }]
        except Exception:
            logger.debug("Wikipedia fetch failed for query='%s'", query)

        return []

    # ------------------------------------------------------------------
    # RSS feed fetching (Google News & others)
    # ------------------------------------------------------------------

    def _fetch_feed(self, feed_url: str, default_lang: str = "ta") -> List[Dict]:
        try:
            response = requests.get(
                feed_url,
                timeout=self.timeout,
                headers={"User-Agent": _next_user_agent()},
            )
            if response.status_code != 200:
                logger.warning(
                    "RSS feed returned status %s for %s",
                    response.status_code, feed_url
                )
                return []
            feed = feedparser.parse(response.content)
        except Exception:
            logger.exception("Failed to fetch/parse RSS feed: %s", feed_url)
            return []

        articles = []
        for entry in feed.entries[:25]:
            img = self._extract_image(entry)
            articles.append({
                "title":    getattr(entry, "title", ""),
                "content":  getattr(entry, "summary", getattr(entry, "description", "")),
                "url":      getattr(entry, "link", ""),
                "image":    img,
                "source":   getattr(feed.feed, "title", "Google News"),
                "date":     getattr(entry, "published", getattr(entry, "updated", "")),
                "language": default_lang,
                "provider": "rss",
            })

        return articles

    def _fetch_tamil_rss(self, queries: List[str]) -> List[Dict]:
        query = next((q for q in queries if q and q.strip()), "")
        if not query:
            return []

        query = query.strip()
        keyword_query = self._extract_tamil_keywords(query)

        articles = self._fetch_feed(
            self._build_tamil_feed_url(keyword_query),
            default_lang="ta",
        )

        # Fallback to full original text if keyword search returns nothing
        if not articles and keyword_query != query:
            logger.info(
                "Tamil RSS search for keywords '%s' returned 0 results; "
                "retrying with the full original claim text.", keyword_query
            )
            articles = self._fetch_feed(
                self._build_tamil_feed_url(query),
                default_lang="ta",
            )

        # Google News RSS entries carry the publisher name inside the title
        for article in articles:
            if not article.get("source") or article["source"] in {"Google News", "Tamil RSS"}:
                title = article.get("title", "")
                if " - " in title:
                    headline, _, publisher = title.rpartition(" - ")
                    article["title"] = headline.strip()
                    article["source"] = publisher.strip()
                else:
                    article["source"] = "Google News (Tamil)"

        return articles

    def _build_tamil_feed_url(self, query: str) -> str:
        encoded_query = urllib.parse.quote(query)
        return self.google_news_tamil_url.format(query=encoded_query)

    # ------------------------------------------------------------------
    # YouTube — Tamil news channels (FIXED: no keyword filter for Tamil)
    # ------------------------------------------------------------------

    def _fetch_youtube_tamil_latest(self, max_per_channel: int = 3) -> List[Dict]:
        """
        Fetches the latest videos from major Tamil news YouTube channels.

        KEY FIX: The old version filtered by English keywords against Tamil-script
        titles — this always returned []. Now we include the latest N videos from
        each channel unconditionally, letting the RAG agent score them for relevance.
        """
        results: List[Dict] = []

        for channel_name, channel_id in self._tamil_yt_channels.items():
            feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            try:
                response = requests.get(
                    feed_url,
                    timeout=self.timeout,
                    headers={"User-Agent": _next_user_agent()},
                )
                if response.status_code != 200:
                    continue
                feed = feedparser.parse(response.content)
            except Exception:
                logger.exception("Failed to fetch YouTube feed for %s", channel_name)
                continue

            count = 0
            for entry in feed.entries[:20]:
                title = getattr(entry, "title", "")
                video_id = getattr(entry, "yt_videoid", "")
                if not video_id:
                    eid = getattr(entry, "id", "")
                    if "yt:video:" in eid:
                        video_id = eid.split("yt:video:")[-1]

                if not video_id or not title:
                    continue

                # YouTube video thumbnail — always available
                thumbnail = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

                results.append({
                    "title":    title,
                    "content":  getattr(entry, "summary", ""),
                    "url":      f"https://www.youtube.com/watch?v={video_id}",
                    "image":    thumbnail,
                    "source":   channel_name,
                    "date":     getattr(entry, "published", ""),
                    "language": "ta",
                    "provider": "youtube",
                })
                count += 1
                if count >= max_per_channel:
                    break

            if len(results) >= 15:
                break

        return results[:15]

    def _fetch_youtube_english(self, keyword_query: str) -> List[Dict]:
        """
        Fetch YouTube videos matching keywords for English queries.
        Uses the YouTube RSS search (unofficial but reliable for top results).
        """
        if not keyword_query or len(keyword_query.strip()) < 3:
            return []

        keywords = [k.lower() for k in keyword_query.split() if len(k) >= 3]
        results: List[Dict] = []

        for channel_name, channel_id in self._tamil_yt_channels.items():
            feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            try:
                response = requests.get(
                    feed_url,
                    timeout=self.timeout,
                    headers={"User-Agent": _next_user_agent()},
                )
                if response.status_code != 200:
                    continue
                feed = feedparser.parse(response.content)
            except Exception:
                continue

            for entry in feed.entries[:15]:
                title = getattr(entry, "title", "")
                video_id = getattr(entry, "yt_videoid", "")
                if not video_id:
                    eid = getattr(entry, "id", "")
                    if "yt:video:" in eid:
                        video_id = eid.split("yt:video:")[-1]

                if not video_id or not title:
                    continue

                title_lower = title.lower()
                if keywords and not any(kw in title_lower for kw in keywords):
                    continue

                thumbnail = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                results.append({
                    "title":    title,
                    "content":  getattr(entry, "summary", ""),
                    "url":      f"https://www.youtube.com/watch?v={video_id}",
                    "image":    thumbnail,
                    "source":   channel_name,
                    "date":     getattr(entry, "published", ""),
                    "language": "ta",
                    "provider": "youtube",
                })

            if len(results) >= 6:
                break

        return results[:6]

    @staticmethod
    def _extract_image(entry) -> str:
        media_content = getattr(entry, "media_content", []) or []
        if media_content:
            return media_content[0].get("url", "")

        thumbnails = getattr(entry, "media_thumbnail", []) or []
        if thumbnails:
            return thumbnails[0].get("url", "")

        # Try to find image in the entry's links
        for link in getattr(entry, "links", []):
            if "image" in link.get("type", ""):
                return link.get("href", "")

        # Note: og:image scraping is done later in _enrich_images_parallel
        # to avoid blocking the RSS loop with sequential HTTP calls.
        return ""