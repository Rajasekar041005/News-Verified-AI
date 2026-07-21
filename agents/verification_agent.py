from collections import Counter
from typing import Dict, List

# Known credible Tamil news outlets. Presence in evidence from these
# sources gets a small confidence boost and lowers the "True" threshold.
_CREDIBLE_TAMIL_SOURCES = {
    "dinamalar", "dinamani", "daily thanthi", "thanthi", "puthiyathalaimurai",
    "polimer", "sun news", "vijay tv", "news18 tamil", "india today tamil",
    "bbc tamil", "the hindu tamil", "vikatan", "ananda vikatan",
    "google news (tamil)",
}

# Minimum score below which we consider the vectoriser to be in
# "hash-ngram mode" (already normalised to 0–1 by RAGAgent).
_HASH_MODE_MAX_SCORE_HINT = 0.30


class VerificationAgent:
    def __init__(self):
        pass

    def verify(self, claim: str, evidence: List[Dict], detected_language: str = "en") -> Dict:
        if len(evidence) == 0:
            return {
                "label": "Needs Verification",
                "confidence_score": 30,
                "explanation": (
                    "No related articles were found in the news database for this claim. "
                    "This may be because the claim is very recent, highly specific, or "
                    "no API keys are configured for additional news sources."
                ),
                "recommendation": (
                    "Add your GROQ_API_KEY, NEWS_API_KEY, or GNEWS_API_KEY in the .env file "
                    "for richer news sources. You can also try rephrasing the claim."
                ),
            }

        is_tamil = detected_language == "ta"

        top_score = float(evidence[0].get("score", 0))
        all_scores = [float(item.get("score", 0)) for item in evidence]
        average_score = sum(all_scores) / max(len(all_scores), 1)
        source_count = len({item.get("source", "").lower() for item in evidence if item.get("source")})
        overlap = self._keyword_overlap(claim, evidence[0])
        score_profile = Counter(self._bucket_score(s) for s in all_scores)

        # Count articles from credible Tamil sources — boosts confidence for
        # Tamil content where cross-language RAG scores are inherently lower.
        credible_tamil_count = sum(
            1 for item in evidence
            if item.get("source", "").lower() in _CREDIBLE_TAMIL_SOURCES
        )

        # ----------------------------------------------------------------
        # Adaptive thresholds
        # ----------------------------------------------------------------
        # Tamil content gets a lower threshold because cross-language (Tamil →
        # English embedding) semantic similarity is structurally lower.
        #
        # Additionally: when RAGAgent has already normalised hash-ngram scores
        # to 0.75 scale, the top score for a genuinely matching article will
        # be around 0.55–0.80.  We detect this mode by checking whether
        # ALL scores are below 0.85 (no cosine similarity will be > 0.85
        # unless the texts are near-identical).
        # ----------------------------------------------------------------
        hash_mode = top_score < 0.85 and average_score < 0.50

        if hash_mode:
            # More lenient thresholds when using the char-ngram fallback
            true_threshold      = 0.42 if is_tamil else 0.50
            false_threshold_top = 0.18 if is_tamil else 0.20
            false_threshold_avg = 0.14 if is_tamil else 0.16
            misleading_threshold = 0.30 if is_tamil else 0.36
        else:
            true_threshold      = 0.58 if is_tamil else 0.72
            false_threshold_top = 0.22 if is_tamil else 0.28
            false_threshold_avg = 0.18 if is_tamil else 0.22
            misleading_threshold = 0.40 if is_tamil else 0.50

        # Extra confidence bonus from credible Tamil outlets
        tamil_bonus = min(credible_tamil_count * 5, 15) if is_tamil else 0

        # ----------------------------------------------------------------
        # Classification logic
        # ----------------------------------------------------------------
        # TRUE: strong similarity + multiple sources + some keyword overlap
        # Credible Tamil sources get a relaxed overlap requirement (0.10 vs 0.15)
        min_overlap = 0.10 if (is_tamil and credible_tamil_count >= 1) else 0.15
        if top_score >= true_threshold and source_count >= 2 and overlap >= min_overlap:
            score = min(98, int((top_score * 55) + (average_score * 25) + (source_count * 8)) + tamil_bonus)
            return {
                "label": "True",
                "confidence_score": score,
                "explanation": (
                    "Multiple high-similarity articles from different sources support the claim."
                    if not is_tamil else
                    "பல்வேறு ஆதாரங்களிலிருந்து உயர்-ஒற்றுமை கட்டுரைகள் கூற்றை உறுதிப்படுத்துகின்றன."
                ),
                "recommendation": "The claim appears credible, but still review the source links before sharing.",
            }

        # FALSE: very weak similarity across the board
        if top_score <= false_threshold_top and average_score <= false_threshold_avg:
            score = min(92, int(30 + (false_threshold_top - top_score) * 120))
            return {
                "label": "False",
                "confidence_score": score,
                "explanation": (
                    "The retrieved evidence has weak semantic overlap with the claim and does not support it."
                    if not is_tamil else
                    "சேகரிக்கப்பட்ட ஆதாரங்கள் கூற்றுடன் பொருந்தவில்லை மற்றும் அதை ஆதரிக்கவில்லை."
                ),
                "recommendation": "Treat this claim as unsupported and avoid sharing until stronger evidence appears.",
            }

        # MISLEADING: moderate–high score but clear signs of missing context or
        # partial match — requires MULTIPLE sources and NOT enough overlap for True.
        # This avoids labelling every moderate-score claim as "Misleading".
        if (
            top_score >= misleading_threshold
            and source_count >= 2
            and overlap < min_overlap  # Not enough keyword overlap to be "True"
        ):
            score = min(90, int((top_score * 45) + (average_score * 20) + (source_count * 6)) + tamil_bonus)
            return {
                "label": "Misleading",
                "confidence_score": score,
                "explanation": (
                    "The claim is partially aligned with the evidence, but available articles suggest missing context or exaggeration."
                    if not is_tamil else
                    "கூற்று ஆதாரத்துடன் பகுதியளவு பொருந்துகிறது, ஆனால் சூழல் முழுமையாக இல்லை."
                ),
                "recommendation": "Check the full articles before trusting the claim; it may omit important context.",
            }

        # NEEDS VERIFICATION — catch-all for anything unclear
        base = max(40, int((top_score * 40) + (source_count * 6) + score_profile.get("mid", 0) * 2))
        # Boost when we have multiple sources even if scores are weak
        if source_count >= 3:
            base = max(base, 45)
        score = min(base + tamil_bonus, 75)
        return {
            "label": "Needs Verification",
            "confidence_score": score,
            "explanation": (
                "Some related evidence was found, but it is not strong enough to confirm the claim."
                if not is_tamil else
                "சில தொடர்புடைய ஆதாரங்கள் கண்டறியப்பட்டன, ஆனால் கூற்றை உறுதிப்படுத்த போதுமானதாக இல்லை."
            ),
            "recommendation": "Collect more sources before making a judgment.",
        }


    def _keyword_overlap(self, claim: str, article: Dict) -> float:
        claim_terms = {token for token in self._tokens(claim) if len(token) > 2}
        article_terms = {
            token for token in self._tokens(
                f"{article.get('title', '')} {article.get('content', '')}"
            )
            if len(token) > 2
        }
        if not claim_terms:
            return 0.0
        return len(claim_terms & article_terms) / len(claim_terms)

    def _tokens(self, text: str) -> List[str]:
        return [
            token.lower()
            for token in text.replace("/", " ").replace("-", " ").split()
            if token.strip()
        ]

    def _bucket_score(self, score: float) -> str:
        if score >= 0.75:
            return "high"
        if score >= 0.45:
            return "mid"
        return "low"