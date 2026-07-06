from functools import lru_cache
from typing import Dict, List, Optional

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.preprocessing import normalize


class RAGAgent:
    def __init__(self):
        self.model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        self._vectorizer = HashingVectorizer(
            n_features=4096,
            analyzer="char_wb",
            ngram_range=(3, 5),
            alternate_sign=False,
            norm=None,
            lowercase=True,
        )

    @lru_cache(maxsize=1)
    def _get_model(self):
        try:
            from sentence_transformers import SentenceTransformer
        except Exception:
            return None

        # Prefer an already-cached local copy (fast, no network needed).
        try:
            return SentenceTransformer(self.model_name, local_files_only=True)
        except Exception:
            pass

        # Fall back to downloading it on first use instead of permanently
        # dropping to the much weaker character-overlap vectorizer below.
        # NOTE: this requires outbound network access at runtime. If your
        # deployment has none, pre-download the model once during build:
        #   python -c "from sentence_transformers import SentenceTransformer as S; \
        #     S('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"
        try:
            return SentenceTransformer(self.model_name)
        except Exception:
            return None

    def _embed(self, texts: List[str], model: Optional[object] = None) -> np.ndarray:
        model = model or self._get_model()
        if model is not None:
            vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return np.asarray(vectors)

        matrix = self._vectorizer.transform(texts)
        return normalize(matrix, norm="l2", axis=1).toarray()

    def retrieve(self, claim: str, articles: List[Dict], model: Optional[object] = None, top_k: int = 5) -> List[Dict]:
        if not claim or not articles:
            return []

        article_texts = [
            f"{article.get('title', '')} {article.get('content', '')}".strip()
            for article in articles
        ]

        claim_vector = self._embed([claim], model)[0]
        article_vectors = self._embed(article_texts, model)

        results: List[Dict] = []

        for article, vector in zip(articles, article_vectors):
            score = float(np.dot(claim_vector, vector))
            if score <= 0:
                continue
            ranked_article = dict(article)
            ranked_article["score"] = round(score, 4)
            results.append(ranked_article)

        if not results:
            for article in articles[:top_k]:
                ranked_article = dict(article)
                ranked_article["score"] = 0.0
                results.append(ranked_article)

        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:top_k]