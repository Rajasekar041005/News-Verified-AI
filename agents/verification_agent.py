from collections import Counter
from typing import Dict, List


class VerificationAgent:
    def __init__(self):
        pass

    def verify(self, claim: str, evidence: List[Dict]) -> Dict:
        if len(evidence) == 0:
            return {
                "label": "Needs Verification",
                "confidence_score": 25,
                "explanation": "No related articles were found.",
                "recommendation": "Try another claim or provide more information.",
            }

        top_score = float(evidence[0].get("score", 0))
        average_score = sum(float(item.get("score", 0)) for item in evidence) / max(len(evidence), 1)
        source_count = len({item.get("source", "") for item in evidence if item.get("source")})
        overlap = self._keyword_overlap(claim, evidence[0])
        score_profile = Counter(self._bucket_score(item.get("score", 0)) for item in evidence)

        if top_score >= 0.78 and source_count >= 2 and overlap >= 0.45:
            return {
                "label": "True",
                "confidence_score": min(98, int((top_score * 55) + (average_score * 25) + (source_count * 8))),
                "explanation": "Multiple high-similarity articles from different sources support the claim.",
                "recommendation": "The claim appears credible, but still review the source links before sharing.",
            }

        if top_score <= 0.28 and average_score <= 0.22:
            return {
                "label": "False",
                "confidence_score": min(92, int(30 + (0.35 - top_score) * 120)),
                "explanation": "The retrieved evidence has weak semantic overlap with the claim and does not support it.",
                "recommendation": "Treat this claim as unsupported and avoid sharing until stronger evidence appears.",
            }

        if top_score >= 0.45 and source_count >= 1:
            return {
                "label": "Misleading",
                "confidence_score": min(90, int((top_score * 45) + (average_score * 20) + (source_count * 6))),
                "explanation": "The claim is partially aligned with the evidence, but the available articles suggest missing context or exaggeration.",
                "recommendation": "Check the full articles before trusting the claim; it may omit important context.",
            }

        return {
            "label": "Needs Verification",
            "confidence_score": max(40, int((top_score * 40) + (source_count * 6) + score_profile.get("mid", 0) * 2)),
            "explanation": "Some related evidence was found, but it is not strong enough to confirm the claim.",
            "recommendation": "Collect more sources before making a judgment.",
        }

    def _keyword_overlap(self, claim: str, article: Dict) -> float:
        claim_terms = {token for token in self._tokens(claim) if len(token) > 2}
        article_terms = {token for token in self._tokens(f"{article.get('title', '')} {article.get('content', '')}") if len(token) > 2}
        if not claim_terms:
            return 0.0
        return len(claim_terms & article_terms) / len(claim_terms)

    def _tokens(self, text: str) -> List[str]:
        return [token.lower() for token in text.replace("/", " ").replace("-", " ").split() if token.strip()]

    def _bucket_score(self, score: float) -> str:
        if score >= 0.75:
            return "high"
        if score >= 0.45:
            return "mid"
        return "low"