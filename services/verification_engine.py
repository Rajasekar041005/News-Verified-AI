import io
import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import easyocr
import numpy as np
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageFilter, ImageOps, ImageEnhance
from dotenv import load_dotenv
from langdetect import DetectorFactory, detect
from deep_translator import GoogleTranslator

from agents.news_agent import NewsAgent
from agents.rag_agent import RAGAgent
from agents.verification_agent import VerificationAgent
from agents.llm_agent import LLMAgent

DetectorFactory.seed = 0
load_dotenv()

logger = logging.getLogger("verification_engine")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# Tamil news sites that are known to be JS-rendered or paywalled.
# For these we expand the tag search to include <div>, <article>, <section>.
_JS_HEAVY_TAMIL_DOMAINS = {
    "dinamalar.com", "dinamani.com", "puthiyathalaimurai.com",
    "polimernews.com", "sun.com", "tamilnadu.com", "nakkeeran.in",
    "tamilmirror.lk", "vikatan.com",
}

# Lower-third chyron region for video: typically bottom 20–30% of frame.
_CHYRON_TOP_FRACTION = 0.65   # crop starts at 65% from top
_CHYRON_BOTTOM_FRACTION = 0.95  # crop ends at 95% from top


class VerificationEngine:
    def __init__(self):
        self.news_agent = NewsAgent()
        self.rag_agent = RAGAgent()
        self.verification_agent = VerificationAgent()
        self.llm_agent = LLMAgent()
        self._ocr_reader = None
        self._translator = None
        self.history_path = Path(os.getenv("HISTORY_PATH", "history.json"))
        self.latest_news_path = Path(os.getenv("LATEST_NEWS_PATH", "latest_news.json"))
        self._ocr_cache: Dict[str, Dict[str, Any]] = {}
        self.url_fetch_timeout = float(os.getenv("URL_FETCH_TIMEOUT_SECONDS", "12"))
        self.video_max_frames = int(os.getenv("VIDEO_MAX_FRAMES", "16"))
        self.video_sample_interval_seconds = float(
            os.getenv("VIDEO_SAMPLE_INTERVAL_SECONDS", "1")
        )

    # ==================================================================
    # TEXT
    # ==================================================================

    async def verify_text(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Verify a news claim entered as text."""

        claim = self.clean_ocr_text(payload.get("content", ""))
        category = payload.get("category", "general")
        language = payload.get("language") or self.detect_language(claim)
        translated_claim = self.translate_if_needed(claim, language)

        # Step 1 — Fetch live news
        articles = self.news_agent.fetch_news(
            claim,
            language,
            english_query=translated_claim or claim,
        )

        # Step 2 — Retrieve similar articles via RAG
        evidence = self.rag_agent.retrieve(translated_claim or claim, articles)

        # Step 3 — Rule-based verification
        verification = self.verification_agent.verify(
            translated_claim or claim,
            evidence,
            detected_language=language,
        )

        # Step 4 — LLM-enhanced explanation (bilingual for Tamil)
        result = self.llm_agent.analyze(
            translated_claim or claim,
            evidence,
            verification,
            original_text=claim if language == "ta" else "",
            detected_language=language,
            source_type=payload.get("source_type", "text"),
            category=category,
        )

        payload_result = {
            "claim": translated_claim or claim,
            "original_text": claim,
            "translation": translated_claim if language == "ta" else "",
            "detected_language": language,
            "source_type": payload.get("source_type", "text"),
            "result": result,
            "evidence": evidence,
            "related_articles": evidence,
            "timeline": self.build_timeline(evidence),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }

        self._save_history(payload_result)
        self._save_latest_news(evidence)
        return payload_result

    # ==================================================================
    # URL
    # ==================================================================

    async def verify_url(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify a news article URL: fetch the page, extract the main article
        text, then run it through the same pipeline as manually-entered text.
        """

        url = payload.get("url", "").strip()

        if not url:
            return self._url_failure(url, "No URL was provided.")

        try:
            title, article_text = self._extract_article_from_url(url)
        except requests.exceptions.Timeout:
            logger.exception("Timed out fetching URL: %s", url)
            return self._url_failure(url, "The URL took too long to respond and timed out.")
        except requests.exceptions.RequestException as e:
            logger.exception("Request error fetching URL: %s", url)
            return self._url_failure(url, f"Could not fetch this URL: {e}")
        except Exception as e:
            logger.exception("Unexpected error fetching URL: %s", url)
            return self._url_failure(url, f"Unexpected error while reading this URL: {e}")

        if not article_text:
            return self._url_failure(
                url,
                "Could not extract readable article text from this page. "
                "It may be paywalled, JavaScript-rendered, or not an article page. "
                "Try pasting the article text directly using the Text tab.",
            )

        claim_text = f"{title}. {article_text}" if title else article_text
        claim_text = self.clean_ocr_text(claim_text)[:4000]

        return await self.verify_text({
            "content": claim_text,
            "source_type": "url",
            "original_text": url,
        })

    def _url_failure(self, url: str, reason: str) -> Dict[str, Any]:
        return {
            "claim": url,
            "result": {
                "label": "Needs Verification",
                "confidence_score": 0,
                "explanation": reason,
                "recommendation": (
                    "Try a different URL, or paste the article text directly using the Text tab."
                ),
                "misinformation_analysis": "URL content could not be analyzed.",
            },
            "evidence": [],
            "related_articles": [],
            "timeline": [],
            "detected_language": "unknown",
            "translation": "",
            "original_text": url,
            "source_type": "url",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }

    def _extract_article_from_url(self, url: str) -> Tuple[str, str]:
        """
        Fetches a URL and extracts a best-effort title + body text.

        Strategy:
        1. Try <article>, <main>, <div class~="article-body"> selectors
           (works well on most CMS-based Tamil news sites).
        2. Fall back to <p> paragraph harvesting.
        3. For known JS-heavy Tamil domains, also try <div>/<span> with
           longer text content.
        """
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lstrip("www.")

        response = requests.get(
            url,
            timeout=self.url_fetch_timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; NewsVerifiedAI/1.0)"},
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()

        # --- Title extraction ---
        title = ""
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()

        # --- Body extraction (layered strategy) ---
        article_text = ""

        # Layer 1: semantic article containers
        for selector in ["article", "main", '[class*="article"]', '[class*="story"]',
                         '[class*="content"]', '[class*="body"]']:
            container = soup.select_one(selector)
            if container:
                text = container.get_text(" ", strip=True)
                if len(text) > 200:
                    article_text = text
                    break

        # Layer 2: paragraph harvesting
        if not article_text:
            paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
            # For Tamil, drop the length threshold (Tamil sentences can be short)
            min_len = 25 if domain in _JS_HEAVY_TAMIL_DOMAINS else 40
            paragraphs = [p for p in paragraphs if len(p) > min_len]
            article_text = " ".join(paragraphs)

        # Layer 3: for JS-heavy Tamil sites, try every <div> / <span> block
        if (not article_text or len(article_text) < 100) and domain in _JS_HEAVY_TAMIL_DOMAINS:
            blocks = []
            for tag in soup.find_all(["div", "span", "section"]):
                text = tag.get_text(" ", strip=True)
                if 50 < len(text) < 3000 and any(
                    "\u0B80" <= ch <= "\u0BFF" for ch in text
                ):
                    blocks.append(text)
            if blocks:
                article_text = " ".join(blocks)

        return title, self.clean_ocr_text(article_text)

    # ==================================================================
    # IMAGE
    # ==================================================================

    async def verify_image(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Verify an uploaded image using OCR."""

        image = Image.open(io.BytesIO(content))
        ocr_data = self.extract_text_from_image(image, filename)
        extracted_text = ocr_data["clean_text"]

        if not extracted_text:
            return {
                "claim": filename,
                "original_text": "",
                "translation": "",
                "detected_language": "unknown",
                "source_type": "image",
                "ocr": ocr_data,
                "ocr_text": "",
                "result": {
                    "label": "Needs Verification",
                    "confidence_score": 0,
                    "explanation": (
                        "No readable text was found in the uploaded image. "
                        "Try uploading a clearer image with visible text."
                    ),
                    "recommendation": "Upload a clearer image with readable English or Tamil text.",
                    "misinformation_analysis": (
                        "OCR could not recover enough text to compare against news sources."
                    ),
                },
                "evidence": [],
                "related_articles": [],
                "timeline": [],
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }

        result = await self.verify_text({
            "content": extracted_text,
            "language": ocr_data["language"],
            "original_text": ocr_data["raw_text"],
            "source_type": "image",
        })
        result["ocr"] = ocr_data
        result["ocr_text"] = extracted_text
        return result

    # ==================================================================
    # VIDEO
    # ==================================================================

    async def verify_video(self, content: bytes, filename: str) -> Dict[str, Any]:
        """
        Verify an uploaded video: sample frames at intervals, OCR each one
        (with extra focus on the lower-third chyron region), and combine
        whatever text was found into a single claim.
        """

        extracted_text, frames_read = self._extract_text_from_video(content, filename)

        if not extracted_text:
            return {
                "claim": filename,
                "original_text": "",
                "translation": "",
                "detected_language": "unknown",
                "source_type": "video",
                "ocr_text": "",
                "result": {
                    "label": "Needs Verification",
                    "confidence_score": 0,
                    "explanation": (
                        "No readable on-screen text was found in the sampled video frames "
                        f"({frames_read} frame(s) checked). "
                        "The video may not have on-screen text, captions, or news chyrons."
                    ),
                    "recommendation": (
                        "Upload a video with clear on-screen text, captions, or a news chyron."
                    ),
                    "misinformation_analysis": (
                        "OCR could not recover enough text from the video to compare against news sources."
                    ),
                },
                "evidence": [],
                "related_articles": [],
                "timeline": [],
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }

        result = await self.verify_text({
            "content": extracted_text,
            "source_type": "video",
        })
        result["ocr_text"] = extracted_text
        return result

    def _extract_text_from_video(
        self, content: bytes, filename: str
    ) -> Tuple[str, int]:
        """
        Writes the uploaded video to a temp file, samples frames at fixed
        intervals, and runs each sampled frame through OCR.

        Two regions are OCR-ed per frame:
        1. Full frame — catches text overlaid anywhere.
        2. Lower-third crop (approx. bottom 25%) — specifically targets the
           news chyron / breaking-news ticker that Tamil news channels place
           there. This was the primary cause of missed text on Tamil news clips.
        """
        suffix = os.path.splitext(filename)[1] or ".mp4"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        collected_lines: List[str] = []
        seen_lines: set = set()
        frames_read = 0

        try:
            capture = cv2.VideoCapture(tmp_path)
            if not capture.isOpened():
                return "", 0

            fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
            total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            frame_step = max(int(fps * self.video_sample_interval_seconds), 1)

            frame_index = 0
            while frames_read < self.video_max_frames:
                if total_frames and frame_index >= total_frames:
                    break

                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                success, frame = capture.read()
                if not success:
                    break

                frames_read += 1
                h, w = frame.shape[:2]

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_full = Image.fromarray(frame_rgb)

                # --- Full frame OCR ---
                ocr_full = self.extract_text_from_image(
                    pil_full, cache_key=f"{filename}:full:{frame_index}"
                )
                self._add_unique_lines(ocr_full.get("clean_text", ""), collected_lines, seen_lines)

                # --- Lower-third chyron crop ---
                top_px = int(h * _CHYRON_TOP_FRACTION)
                bot_px = int(h * _CHYRON_BOTTOM_FRACTION)
                if bot_px > top_px:
                    pil_chyron = pil_full.crop((0, top_px, w, bot_px))
                    ocr_chyron = self.extract_text_from_image(
                        pil_chyron,
                        cache_key=f"{filename}:chyron:{frame_index}",
                    )
                    self._add_unique_lines(
                        ocr_chyron.get("clean_text", ""), collected_lines, seen_lines
                    )

                frame_index += frame_step

            capture.release()
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        return self.clean_ocr_text(" ".join(collected_lines)), frames_read

    def _add_unique_lines(
        self, text: str, collected: List[str], seen: set
    ) -> None:
        if text and text.lower() not in seen:
            seen.add(text.lower())
            collected.append(text)

    # ==================================================================
    # OCR
    # ==================================================================

    def extract_text_from_image(
        self, image: Image.Image, cache_key: str = "image"
    ) -> Dict[str, Any]:
        cached = self._ocr_cache.get(cache_key)
        if cached:
            return cached

        image = self._prepare_image(image)
        reader = self.get_ocr_reader()
        image_np = np.array(image)

        raw_text = ""
        source = "tesseract"

        if reader is not None:
            try:
                result = reader.readtext(image_np, detail=1, paragraph=False)
                # Filter out low-confidence detections (< 30%)
                result = [(bbox, text, conf) for bbox, text, conf in result if conf >= 0.3]
                raw_text = " ".join(text for (_, text, _) in result)
                if raw_text.strip():
                    source = "easyocr"
            except Exception:
                logger.exception("easyocr.readtext() failed for cache_key=%s", cache_key)
                raw_text = ""
        else:
            logger.warning(
                "easyocr reader unavailable for cache_key=%s; falling back to tesseract",
                cache_key,
            )

        if not raw_text.strip():
            raw_text = self._read_with_tesseract(image)

        # --- Try harder on small/dark images ---
        if not raw_text.strip():
            enhanced = self._aggressive_enhance(image)
            if reader is not None:
                try:
                    result = reader.readtext(np.array(enhanced))
                    raw_text = " ".join(text for (_, text, _) in result)
                    source = "easyocr-enhanced"
                except Exception:
                    pass
            if not raw_text.strip():
                raw_text = self._read_with_tesseract(enhanced)

        cleaned_text = self.clean_ocr_text(raw_text)
        language = self.detect_language(cleaned_text)
        payload = {
            "raw_text": raw_text,
            "clean_text": cleaned_text,
            "language": language,
            "source": source,
        }
        self._ocr_cache[cache_key] = payload
        return payload

    def get_ocr_reader(self):
        if self._ocr_reader is None:
            try:
                self._ocr_reader = easyocr.Reader(
                    ["en", "ta"],
                    gpu=False,
                    verbose=False,
                )
            except Exception:
                logger.exception(
                    "Failed to load easyocr.Reader(['en','ta']). Common cause: "
                    "missing model weights (needs internet on first run) or a "
                    "corrupt model cache. Falling back to Tesseract for OCR."
                )
                self._ocr_reader = False
        return self._ocr_reader or None

    def _read_with_tesseract(self, image: Image.Image) -> str:
        try:
            import pytesseract
        except Exception:
            logger.exception("pytesseract is not installed; no OCR fallback available")
            return ""

        try:
            # Try Tamil + English first; fall back to English-only if the
            # 'tam' Tesseract language pack is not installed.
            try:
                return pytesseract.image_to_string(
                    image, lang="eng+tam", config="--oem 3 --psm 6"
                )
            except Exception:
                logger.warning(
                    "Tesseract 'tam' language pack not found; falling back to 'eng' only."
                )
                return pytesseract.image_to_string(
                    image, lang="eng", config="--oem 3 --psm 6"
                )
        except Exception:
            logger.exception("pytesseract.image_to_string() failed entirely.")
            return ""

    def _prepare_image(self, image: Image.Image) -> Image.Image:
        """Standard preprocessing: normalise mode, correct orientation,
        auto-contrast, sharpen. Works for most news screenshots."""
        if image.mode != "RGB":
            image = image.convert("RGB")
        image = ImageOps.exif_transpose(image)
        image = ImageOps.autocontrast(image, cutoff=1)
        image = ImageEnhance.Sharpness(image).enhance(1.8)
        image = ImageEnhance.Contrast(image).enhance(1.3)
        return image

    def _aggressive_enhance(self, image: Image.Image) -> Image.Image:
        """
        More aggressive enhancement for dark, low-contrast, or
        compressed images (common in Tamil news screenshots from WhatsApp).
        Converts to grayscale → adaptive threshold → back to RGB.
        """
        gray = image.convert("L")
        gray = ImageOps.autocontrast(gray, cutoff=2)
        gray = ImageEnhance.Contrast(gray).enhance(2.0)
        gray = gray.filter(ImageFilter.SHARPEN)
        # Binarise: anything below mid-gray → black, above → white
        threshold = 128
        gray = gray.point(lambda p: 255 if p > threshold else 0)
        return gray.convert("RGB")

    # ==================================================================
    # Language detection & translation
    # ==================================================================

    def detect_language(self, text: str) -> str:
        text = self.clean_ocr_text(text)
        if not text:
            return "unknown"

        # Count Tamil Unicode block characters (U+0B80–U+0BFF).
        # Even a few Tamil chars should force Tamil classification because
        # mixed Tamil-English text (very common in Tamil news) was previously
        # being misclassified as English.
        tamil_chars = sum(1 for ch in text if "\u0B80" <= ch <= "\u0BFF")
        total_alpha = sum(1 for ch in text if ch.isalpha())

        if tamil_chars > 0 and total_alpha > 0:
            if tamil_chars / total_alpha >= 0.10:
                return "ta"

        try:
            detected = detect(text)
            return detected if detected in {"en", "ta"} else "en"
        except Exception:
            return "en"

    def translate_if_needed(self, text: str, language: str) -> str:
        if language != "ta" or not text:
            return text
        translator = self.get_translator()
        if translator is None:
            return text
        try:
            # deep_translator has a 5000-char limit per call.
            if len(text) > 4500:
                text = text[:4500]
            return translator.translate(text)
        except Exception:
            logger.exception("Translation failed; returning original Tamil text")
            return text

    def get_translator(self):
        if self._translator is None:
            try:
                self._translator = GoogleTranslator(source="auto", target="en")
            except Exception:
                self._translator = False
        return self._translator or None

    # ==================================================================
    # Utilities
    # ==================================================================

    def clean_ocr_text(self, text: str) -> str:
        if not isinstance(text, str):
            return ""
        # Remove zero-width characters
        text = re.sub(r"[\u200b\u200c\u200d]", "", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def build_timeline(self, evidence: List[Dict]) -> List[Dict]:
        timeline = []
        for item in evidence[:8]:
            timeline.append({
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "date": item.get("date", ""),
                "url": item.get("url", ""),
            })
        return timeline

    def _save_history(self, payload: Dict[str, Any]) -> None:
        try:
            if self.history_path.parent != Path("."):
                os.makedirs(self.history_path.parent, exist_ok=True)
            history = []
            if self.history_path.exists():
                with self.history_path.open("r", encoding="utf-8") as handle:
                    history = json.load(handle)
            history.append(payload)
            with self.history_path.open("w", encoding="utf-8") as handle:
                json.dump(history, handle, ensure_ascii=False, indent=2)
        except Exception:
            logger.exception("Failed to save history to %s", self.history_path)

    def _save_latest_news(self, articles: List[Dict]) -> None:
        try:
            if self.latest_news_path.parent != Path("."):
                os.makedirs(self.latest_news_path.parent, exist_ok=True)
            with self.latest_news_path.open("w", encoding="utf-8") as handle:
                json.dump(articles[:20], handle, ensure_ascii=False, indent=2)
        except Exception:
            logger.exception("Failed to save latest news to %s", self.latest_news_path)