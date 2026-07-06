import json
import os
from typing import Dict, List

from dotenv import load_dotenv

load_dotenv()


class LLMAgent:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "")
        self.model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    def analyze(
        self,
        claim: str,
        evidence: List[Dict],
        verification_result: Dict,
        original_text: str = "",
        detected_language: str = "en",
        source_type: str = "text",
        category: str = "general",
    ) -> Dict:
        if not self.api_key:
            return self._fallback_analysis(claim, evidence, verification_result, detected_language, source_type)

        try:
            from groq import Groq
        except Exception:
            return self._fallback_analysis(claim, evidence, verification_result, detected_language, source_type)

        client = Groq(api_key=self.api_key)
        evidence_payload = [
            {
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "date": item.get("date", ""),
                "url": item.get("url", ""),
                "score": item.get("score", 0),
            }
            for item in evidence[:8]
        ]

        prompt = f"""
You are an expert multilingual fact-checking analyst.
Return a strict JSON object with these keys:
label, confidence_score, explanation, recommendation, misinformation_analysis.

Context:
- Claim: {claim}
- Original text: {original_text}
- Detected language: {detected_language}
- Source type: {source_type}
- Category: {category}
- Preliminary label: {verification_result.get('label', '')}
- Preliminary confidence: {verification_result.get('confidence_score', 0)}
- Evidence: {json.dumps(evidence_payload, ensure_ascii=False)}

Rules:
- label must be one of True, False, Misleading, Needs Verification.
- explanation must be concise but specific.
- misinformation_analysis must explain what could be misleading, missing, exaggerated, or unsupported.
- recommendation must be a direct action for the user.
""".strip()

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You generate structured fact-checking analysis."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=700,
        )

        content = response.choices[0].message.content.strip()
        parsed = self._parse_json(content)
        if not parsed:
            return self._fallback_analysis(claim, evidence, verification_result, detected_language, source_type)

        return {
            "label": parsed.get("label", verification_result.get("label", "Needs Verification")),
            "confidence_score": int(parsed.get("confidence_score", verification_result.get("confidence_score", 0))),
            "explanation": parsed.get("explanation", verification_result.get("explanation", "")),
            "recommendation": parsed.get("recommendation", verification_result.get("recommendation", "")),
            "misinformation_analysis": parsed.get("misinformation_analysis", ""),
        }

    def _fallback_analysis(
        self,
        claim: str,
        evidence: List[Dict],
        verification_result: Dict,
        detected_language: str,
        source_type: str,
    ) -> Dict:
        label = verification_result.get("label", "Needs Verification")
        if label == "True":
            explanation = f"The claim is supported by {len(evidence)} related articles with strong semantic overlap."
            misinformation_analysis = "No strong misinformation pattern was detected."
        elif label == "False":
            explanation = "The evidence has weak support for the claim and does not confirm it."
            misinformation_analysis = "The claim appears unsupported or fabricated relative to the retrieved sources."
        elif label == "Misleading":
            explanation = "The claim matches some evidence, but the context appears incomplete or overstated."
            misinformation_analysis = "The statement may be technically related to real news but framed in a misleading way."
        else:
            explanation = "The available evidence is not strong enough to confirm the claim."
            misinformation_analysis = "There is insufficient corroboration to classify the claim with confidence."

        return {
            "label": label,
            "confidence_score": verification_result.get("confidence_score", 0),
            "explanation": explanation,
            "recommendation": verification_result.get("recommendation", "Review source links before sharing."),
            "misinformation_analysis": misinformation_analysis,
        }

    def _parse_json(self, content: str):
        try:
            return json.loads(content)
        except Exception:
            pass

        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(content[start : end + 1])
            except Exception:
                return None
        return None