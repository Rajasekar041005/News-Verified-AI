import io
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import easyocr
import numpy as np
from PIL import Image, ImageFilter, ImageOps
from dotenv import load_dotenv
from langdetect import DetectorFactory, detect
from deep_translator import GoogleTranslator

from agents.news_agent import NewsAgent
from agents.rag_agent import RAGAgent
from agents.verification_agent import VerificationAgent
from agents.llm_agent import LLMAgent

DetectorFactory.seed = 0
load_dotenv()

class VerificationEngine:
    def __init__(self):
        self.news_agent = NewsAgent()
        self.rag_agent = RAGAgent()
        self.verification_agent = VerificationAgent()
        self.llm_agent = LLMAgent()
        self._ocr_reader = None
        self._translator = None
        self.history_path = Path("data/history.json")
        self.latest_news_path = Path("data/latest_news.json")
        self._ocr_cache: Dict[str, Dict[str, Any]] = {}

    async def verify_text(self, payload):
        """
        Verify a news claim entered as text.
        """

        claim = self.clean_ocr_text(payload.get("content", ""))
        category = payload.get("category", "general")
        language = payload.get("language") or self.detect_language(claim)
        translated_claim = self.translate_if_needed(claim, language)

        # Step 1 - Fetch live news
        # `claim` (original language) is used for Tamil RSS matching.
        # `translated_claim` (English) is used for NewsAPI matching.
        # Passing only one of these to both sources is what was causing
        # Tamil claims and "related articles" to consistently come back empty.
        articles = self.news_agent.fetch_news(
            claim,
            language,
            english_query=translated_claim or claim,
        )

        # Step 2 - Retrieve similar articles
        evidence = self.rag_agent.retrieve(translated_claim or claim, articles)

        # Step 3 - Verify claim
        verification = self.verification_agent.verify(
            translated_claim or claim,
            evidence
        )

        # Step 4 - AI explanation
        result = self.llm_agent.analyze(
            translated_claim or claim,
            evidence,
            verification
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

    async def verify_url(self, payload):
        """
        Verify a news article URL.
        """

        url = payload.get("url", "")

        return {
            "claim": url,
            "result": {
                "label": "Needs Verification",
                "confidence_score": 50,
                "explanation": "URL verification will be implemented next.",
                "recommendation": "Feature under development.",
                "misinformation_analysis": "URL analysis is not yet enabled."
            },
            "evidence": [],
            "related_articles": [],
            "timeline": [],
            "detected_language": "unknown",
            "translation": "",
            "original_text": url,
            "source_type": "url",
        }

    async def verify_image(self, content, filename):
        """
        Verify an uploaded image using OCR.
        """

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
                "result": {
                    "label": "Needs Verification",
                    "confidence_score": 0,
                    "explanation": "No readable text was found in the uploaded image.",
                    "recommendation": "Upload a clearer image with readable English or Tamil text.",
                    "misinformation_analysis": "OCR could not recover enough text to compare against news sources.",
                },
                "evidence": [],
                "related_articles": [],
                "timeline": [],
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }

        return await self.verify_text({
            "content": extracted_text,
            "language": ocr_data["language"],
            "original_text": ocr_data["raw_text"],
            "source_type": "image",
        })

    async def verify_video(self, content, filename):
        """
        Verify an uploaded video.
        """

        # TODO:
        # Extract frames and OCR them.
        extracted_text = "Text extracted from video"

        return await self.verify_text({
            "content": extracted_text,
            "source_type": "video"
        })

    def extract_text_from_image(self, image: Image.Image, cache_key: str = "image") -> Dict[str, Any]:
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
                result = reader.readtext(image_np)
                raw_text = " ".join([text for (_, text, _) in result])
                if raw_text.strip():
                    source = "easyocr"
            except Exception:
                raw_text = ""

        if not raw_text.strip():
            raw_text = self._read_with_tesseract(image)

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
                self._ocr_reader = easyocr.Reader(['en', 'ta'], gpu=False)
            except Exception:
                self._ocr_reader = False
        return self._ocr_reader or None

    def _read_with_tesseract(self, image: Image.Image) -> str:
        try:
            import pytesseract
        except Exception:
            return ""

        try:
            return pytesseract.image_to_string(image, lang="eng+tam", config="--oem 3 --psm 6")
        except Exception:
            return ""

    def _prepare_image(self, image: Image.Image) -> Image.Image:
        if image.mode != "RGB":
            image = image.convert("RGB")
        image = ImageOps.exif_transpose(image)
        image = ImageOps.autocontrast(image)
        image = image.filter(ImageFilter.SHARPEN)
        return image

    def detect_language(self, text: str) -> str:
        text = self.clean_ocr_text(text)
        if not text:
            return "unknown"
        tamil_chars = sum(1 for ch in text if "\u0B80" <= ch <= "\u0BFF")
        if tamil_chars > 0:
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
            return translator.translate(text)
        except Exception:
            return text

    def get_translator(self):
        if self._translator is None:
            try:
                self._translator = GoogleTranslator(source="auto", target="en")
            except Exception:
                self._translator = False
        return self._translator or None

    def clean_ocr_text(self, text: str) -> str:
        if not isinstance(text, str):
            return ""
        text = re.sub(r"[\u200b\u200c\u200d]", "", text)
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
            os.makedirs("data", exist_ok=True)
            history = []
            if self.history_path.exists():
                with self.history_path.open("r", encoding="utf-8") as handle:
                    history = json.load(handle)
            history.append(payload)
            with self.history_path.open("w", encoding="utf-8") as handle:
                json.dump(history, handle, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _save_latest_news(self, articles: List[Dict]) -> None:
        try:
            os.makedirs("data", exist_ok=True)
            with self.latest_news_path.open("w", encoding="utf-8") as handle:
                json.dump(articles[:20], handle, ensure_ascii=False, indent=2)
        except Exception:
            pass