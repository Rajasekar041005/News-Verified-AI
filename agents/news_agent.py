import os
import re
import urllib.parse
from functools import lru_cache
from typing import Dict, List, Optional

import feedparser
import requests
from dotenv import load_dotenv

load_dotenv()

_STOPWORDS = {
    "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "with",
    "of", "is", "are", "was", "were", "said", "that", "this", "from", "by",
    "as", "if", "would", "be", "open", "holding", "such", "according",
    "meeting", "during",
}


class NewsAgent:
    def __init__(self):
        self.api_key = os.getenv("NEWS_API_KEY", "")
        self.timeout = float(os.getenv("NEWS_TIMEOUT_SECONDS", "12"))

        # NOTE: The individual Tamil outlet RSS URLs that used to live here
        # (dailythanthi.com/rss, dinamalar.com/rss.php, dinamani.com/rss_feed/,
        # tamil.news18.com/rss, puthiyathalaimurai.com/rss) were all confirmed
        # dead (404s, or redirects to the plain homepage instead of XML) as of
        # 2026-07. Rather than depend on any single outlet's feed staying
        # alive, Tamil results now come from Google News' RSS search, which
        # aggregates many Tamil outlets at once and is filtered server-side
        # by the query itself.
        #
        # This is an unofficial, undocumented Google endpoint (its robots.txt
        # disallows crawlers, though feed-reader-style consumption via
        # requests/feedparser is the standard way it's used in practice).
        # Google could change or restrict it without notice — if that
        # happens, swap in a paid Tamil-language news API instead
        # (e.g. NewsData.io or GNews, both of which support "ta").
        self.google_news_tamil_url = "https://news.google.com/rss/search?q={query}&hl=ta&gl=IN&ceid=IN:ta"

    def fetch_news(
        self,
        query: str,
        language: str = "en",
        english_query: Optional[str] = None,
    ) -> List[Dict]:
        """
        query: the claim text in its ORIGINAL language — used to match
               against Tamil RSS feeds (which are written in Tamil script).
        english_query: the claim translated to English (if applicable) —
               used for NewsAPI, which only matches Latin-script keywords.
               Falls back to `query` when not provided.
        """
        articles: List[Dict] = []

        newsapi_query = english_query or query
        keyword_query = self._extract_keywords(newsapi_query)

        if self.api_key:
            articles.extend(self._fetch_newsapi(keyword_query, "en"))

        # Tamil RSS matching uses the ORIGINAL (untranslated) claim text,
        # since these feeds are written in Tamil — matching translated
        # English keywords against them will never hit.
        articles.extend(self._fetch_tamil_rss([query]))

        deduped: List[Dict] = []
        seen = set()

        for article in articles:
            fingerprint = (
                article.get("title", "").strip().lower(),
                article.get("url", "").strip().lower(),
            )
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            deduped.append(article)

        return deduped[:25]

    def _extract_keywords(self, text: str, max_terms: int = 6) -> str:
        """
        NewsAPI's /v2/everything does near-literal keyword matching, not
        semantic search. Passing a full sentence as `q` frequently returns
        zero results. This pulls out proper nouns / key terms instead.
        """
        if not text:
            return text

        words = re.findall(r"[A-Za-z][A-Za-z'\-]*", text)

        capitalized = [w for w in words if w[0].isupper() and w.lower() not in _STOPWORDS]
        others = [w for w in words if w.lower() not in _STOPWORDS and w not in capitalized]

        ordered: List[str] = []
        seen = set()
        for w in capitalized + others:
            lw = w.lower()
            if lw in seen:
                continue
            seen.add(lw)
            ordered.append(w)
            if len(ordered) >= max_terms:
                break

        return " ".join(ordered) if ordered else text

    @lru_cache(maxsize=128)
    def _fetch_newsapi(self, query: str, language: str) -> List[Dict]:
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 10,
            "apiKey": self.api_key,
        }
        try:
            response = requests.get(
                "https://newsapi.org/v2/everything",
                params=params,
                timeout=self.timeout,
            )
        except Exception:
            return []

        if response.status_code != 200:
            return []

        data = response.json()
        articles = []

        for article in data.get("articles", []):
            articles.append({
                "title": article.get("title", ""),
                "content": article.get("description", ""),
                "url": article.get("url", ""),
                "image": article.get("urlToImage", ""),
                "source": article.get("source", {}).get("name", "NewsAPI"),
                "date": article.get("publishedAt", ""),
                "language": language,
                "provider": "newsapi",
            })

        return articles

    @lru_cache(maxsize=256)
    def _fetch_feed(self, feed_url: str) -> List[Dict]:
        try:
            response = requests.get(feed_url, timeout=self.timeout, headers={"User-Agent": "Mozilla/5.0"})
            if response.status_code != 200:
                return []
            feed = feedparser.parse(response.content)
        except Exception:
            return []

        articles = []
        for entry in feed.entries[:15]:
            articles.append({
                "title": getattr(entry, "title", ""),
                "content": getattr(entry, "summary", getattr(entry, "description", "")),
                "url": getattr(entry, "link", ""),
                "image": self._extract_image(entry),
                "source": getattr(feed.feed, "title", "Tamil RSS"),
                "date": getattr(entry, "published", getattr(entry, "updated", "")),
                "language": "ta",
                "provider": "rss",
            })

        return articles

    def _fetch_tamil_rss(self, queries: List[str]) -> List[Dict]:
        query = next((q for q in queries if q and q.strip()), "")
        if not query:
            return []

        encoded_query = urllib.parse.quote(query.strip())
        feed_url = self.google_news_tamil_url.format(query=encoded_query)

        articles = self._fetch_feed(feed_url)

        # Google News RSS entries carry the publisher name inside the title
        # (e.g. "Headline - Dinamalar"); pull that out as the source when
        # feedparser didn't already give us one.
        for article in articles:
            if not article.get("source") or article["source"] == "Tamil RSS":
                title = article.get("title", "")
                if " - " in title:
                    headline, _, publisher = title.rpartition(" - ")
                    article["title"] = headline.strip()
                    article["source"] = publisher.strip()
                else:
                    article["source"] = "Google News (Tamil)"

        return articles

    def _matches_queries(self, article: Dict, queries: List[str]) -> bool:
        haystack = f"{article.get('title', '')} {article.get('content', '')}".lower()
        if not queries:
            return True

        for query in queries:
            terms = [term.strip().lower() for term in query.split() if len(term.strip()) > 1]
            if not terms:
                continue
            score = sum(1 for term in terms if term in haystack)
            if score >= 1:
                return True

        return False

    @staticmethod
    def _extract_image(entry) -> str:
        media_content = getattr(entry, "media_content", []) or []
        if media_content:
            return media_content[0].get("url", "")

        thumbnails = getattr(entry, "media_thumbnail", []) or []
        if thumbnails:
            return thumbnails[0].get("url", "")

        return ""