import json
import os
from typing import Dict, List

from dotenv import load_dotenv

load_dotenv()

# Models in preference order — first one that works (key present + no import
# error) wins. mixtral-8x7b-32768 has stronger multilingual (Tamil) coverage
# than the tiny 8b instant model; 70b versatile is best but slowest.
_GROQ_MODEL_PREFERENCE = [
    "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768",
    "llama-3.1-8b-instant",
]


class LLMAgent:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "")
        # Allow env override; fall back to the preference list at runtime.
        self.model = os.getenv("GROQ_MODEL", "")

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
            return self._fallback_analysis(
                claim, evidence, verification_result, detected_language, source_type
            )

        try:
            from groq import Groq
        except Exception:
            return self._fallback_analysis(
                claim, evidence, verification_result, detected_language, source_type
            )

        client = Groq(api_key=self.api_key)
        model = self._resolve_model(client)

        evidence_payload = [
            {
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "date": item.get("date", ""),
                "url": item.get("url", ""),
                "score": item.get("score", 0),
                "language": item.get("language", "en"),
            }
            for item in evidence[:8]
        ]

        is_tamil = detected_language == "ta"
        bilingual_instruction = ""
        if is_tamil:
            bilingual_instruction = """
IMPORTANT: The original claim is in Tamil. You MUST provide BOTH:
- English fields: explanation, recommendation, misinformation_analysis
- Tamil fields: tamil_explanation, tamil_recommendation (same content translated to Tamil)
The UI will display both languages side-by-side for Tamil users.
"""

        prompt = f"""
You are an expert multilingual fact-checking analyst specialising in Indian news, 
Tamil Nadu politics, and Tamil-language media.
Return a strict JSON object with these keys:
  label, confidence_score, explanation, recommendation, misinformation_analysis
  {', tamil_explanation, tamil_recommendation' if is_tamil else ''}

Context:
- Claim (English): {claim}
- Original text (Tamil): {original_text if original_text else '(same as claim)'}
- Detected language: {detected_language}
- Source type: {source_type}
- Category: {category}
- Preliminary label: {verification_result.get('label', '')}
- Preliminary confidence: {verification_result.get('confidence_score', 0)}
- Evidence articles: {json.dumps(evidence_payload, ensure_ascii=False)}

Rules:
- label must be exactly one of: True, False, Misleading, Needs Verification
- confidence_score must be an integer 0-100
- explanation must be concise but specific (2-4 sentences)
- misinformation_analysis must explain what could be misleading, missing, exaggerated, or unsupported
- recommendation must be a direct, actionable instruction for the user
- If evidence is from Tamil outlets (Dinamalar, Dinamani, Daily Thanthi, etc.), treat them as credible Tamil-language sources
{bilingual_instruction}
Return ONLY the JSON object, no markdown fences or extra text.
""".strip()

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a Tamil-English bilingual fact-checking AI. "
                            "You generate structured JSON analysis of news claims."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=1200,
            )

            content = response.choices[0].message.content.strip()
            parsed = self._parse_json(content)
            if not parsed:
                return self._fallback_analysis(
                    claim, evidence, verification_result, detected_language, source_type
                )

            result = {
                "label": parsed.get("label", verification_result.get("label", "Needs Verification")),
                "confidence_score": int(
                    parsed.get("confidence_score", verification_result.get("confidence_score", 0))
                ),
                "explanation": parsed.get("explanation", verification_result.get("explanation", "")),
                "recommendation": parsed.get(
                    "recommendation", verification_result.get("recommendation", "")
                ),
                "misinformation_analysis": parsed.get("misinformation_analysis", ""),
            }

            if is_tamil:
                result["tamil_explanation"] = parsed.get("tamil_explanation", "")
                result["tamil_recommendation"] = parsed.get("tamil_recommendation", "")

            return result

        except Exception:
            return self._fallback_analysis(
                claim, evidence, verification_result, detected_language, source_type
            )

    # ------------------------------------------------------------------
    # Model resolution
    # ------------------------------------------------------------------

    def _resolve_model(self, client) -> str:
        """
        If the user set GROQ_MODEL, use it directly.
        Otherwise walk the preference list and pick the first model that
        exists in the user's Groq account (avoids 404 / model-not-found
        errors when newer models are unavailable on a free tier).
        """
        if self.model:
            return self.model

        try:
            available = {m.id for m in client.models.list().data}
        except Exception:
            # If we can't list models, just try the top preference.
            return _GROQ_MODEL_PREFERENCE[0]

        for candidate in _GROQ_MODEL_PREFERENCE:
            if candidate in available:
                return candidate

        return _GROQ_MODEL_PREFERENCE[-1]

    # ------------------------------------------------------------------
    # Fallback (no API key or network error)
    # ------------------------------------------------------------------

    def _fallback_analysis(
        self,
        claim: str,
        evidence: List[Dict],
        verification_result: Dict,
        detected_language: str,
        source_type: str,
    ) -> Dict:
        label = verification_result.get("label", "Needs Verification")
        is_tamil = detected_language == "ta"

        if label == "True":
            explanation = (
                f"The claim is supported by {len(evidence)} related article(s) "
                "with strong semantic overlap from credible sources."
            )
            tamil_explanation = (
                f"இந்த செய்தி {len(evidence)} தொடர்புடைய கட்டுரைகளால் "
                "நம்பகமான ஆதாரங்களுடன் உறுதிப்படுத்தப்பட்டுள்ளது."
            )
            misinformation_analysis = "No strong misinformation pattern was detected."
            recommendation = "The claim appears credible. Still verify with the source links before sharing."
            tamil_recommendation = "செய்தி நம்பகமானதாக தெரிகிறது. பகிர்வதற்கு முன் மூல இணைப்புகளை சரிபார்க்கவும்."
        elif label == "False":
            explanation = (
                "The retrieved evidence has weak semantic overlap with the claim "
                "and does not support it."
            )
            tamil_explanation = (
                "சேகரிக்கப்பட்ட ஆதாரங்கள் இந்த கூற்றை ஆதரிக்கவில்லை. "
                "இது தவறான செய்தியாக இருக்கலாம்."
            )
            misinformation_analysis = "The claim appears unsupported or fabricated relative to the retrieved sources."
            recommendation = "Treat this claim as unsupported. Do not share until stronger evidence is found."
            tamil_recommendation = "இந்த கூற்றை ஆதரிக்கும் ஆதாரம் இல்லை. வலுவான சான்று கிடைக்கும் வரை பகிர வேண்டாம்."
        elif label == "Misleading":
            explanation = (
                "The claim partially matches evidence, but the available articles "
                "suggest missing context or exaggeration."
            )
            tamil_explanation = (
                "கூற்று சில ஆதாரங்களுடன் பகுதியளவு பொருந்துகிறது, "
                "ஆனால் சூழல் முழுமையாக இல்லை அல்லது மிகைப்படுத்தப்பட்டுள்ளது."
            )
            misinformation_analysis = "The statement may relate to real news but is framed in a misleading way."
            recommendation = "Check the full articles before trusting the claim; it may omit important context."
            tamil_recommendation = (
                "நம்புவதற்கு முன் முழு கட்டுரைகளை படிக்கவும்; "
                "முக்கியமான தகவல்கள் தவிர்க்கப்பட்டிருக்கலாம்."
            )
        else:
            explanation = "The available evidence is not strong enough to confirm or deny the claim."
            tamil_explanation = (
                "கூற்றை உறுதிப்படுத்த அல்லது மறுக்க போதுமான ஆதாரம் இல்லை."
            )
            misinformation_analysis = "Insufficient corroboration to classify this claim with confidence."
            recommendation = "Collect more sources and cross-check before making a judgment."
            tamil_recommendation = "முடிவு எடுப்பதற்கு முன் மேலும் ஆதாரங்களை சேகரித்து சரிபார்க்கவும்."

        result = {
            "label": label,
            "confidence_score": verification_result.get("confidence_score", 0),
            "explanation": explanation,
            "recommendation": recommendation,
            "misinformation_analysis": misinformation_analysis,
        }

        if is_tamil:
            result["tamil_explanation"] = tamil_explanation
            result["tamil_recommendation"] = tamil_recommendation

        return result

    # ------------------------------------------------------------------
    # JSON parsing helper
    # ------------------------------------------------------------------

    def _parse_json(self, content: str):
        try:
            return json.loads(content)
        except Exception:
            pass

        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(content[start: end + 1])
            except Exception:
                return None
        return None