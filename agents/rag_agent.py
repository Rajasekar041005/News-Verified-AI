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
        # Track which backend is actually being used so scores can be
        # normalised appropriately in retrieve().
        self._using_transformers: Optional[bool] = None

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
        try:
            return SentenceTransformer(self.model_name)
        except Exception:
            return None

    def _embed(self, texts: List[str], model: Optional[object] = None):
        """Return (vectors, used_transformers) tuple."""
        model = model or self._get_model()
        if model is not None:
            vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return np.asarray(vectors), True

        matrix = self._vectorizer.transform(texts)
        return normalize(matrix, norm="l2", axis=1).toarray(), False

    def retrieve(
        self,
        claim: str,
        articles: List[Dict],
        model: Optional[object] = None,
        top_k: int = 10,
    ) -> List[Dict]:
        if not claim:
            return []
        if not articles:
            return []

        article_texts = [
            f"{article.get('title', '')} {article.get('content', '')}".strip()
            for article in articles
        ]

        claim_vec, used_transformers = self._embed([claim], model)
        claim_vector = claim_vec[0]
        article_vectors, _ = self._embed(article_texts, model)

        self._using_transformers = used_transformers

        raw_scores = [
            float(np.dot(claim_vector, article_vectors[i]))
            for i in range(len(articles))
        ]

        # ----------------------------------------------------------------
        # Score normalisation
        # Hash-ngram scores live in a much lower range (0.01–0.25) than
        # sentence-transformer cosine similarities (0.0–1.0).  Rescale so
        # the VerificationAgent thresholds (calibrated for transformers)
        # remain meaningful regardless of which backend we're using.
        # ----------------------------------------------------------------
        if not used_transformers and raw_scores:
            max_score = max(raw_scores) or 1.0
            # Scale so the best-matching article gets score ≈ 0.75
            # (well inside the "Misleading / True" zone).
            scale_factor = 0.75 / max_score
            scores = [min(s * scale_factor, 1.0) for s in raw_scores]
        else:
            scores = raw_scores

        results: List[Dict] = []
        for article, score in zip(articles, scores):
            ranked = dict(article)
            # Use a soft floor of 0.01 — never hard-drop articles.
            ranked["score"] = round(max(score, 0.01), 4)
            results.append(ranked)

        results.sort(key=lambda item: item["score"], reverse=True)

        # Always return at least min(top_k, len(articles)) items so
        # the verification pipeline is never starved of evidence.
        return results[:max(top_k, min(5, len(results)))]