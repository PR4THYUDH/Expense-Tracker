import json
import re
import os
import base64
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Any, Optional
from django.conf import settings

# Attempt import of official Anthropic SDK
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None
    ANTHROPIC_AVAILABLE = False


class ClaudeAIService:
    """
    Dedicated AI Service Layer for Anthropic Claude integration.
    Handles API communication, strict schema prompt enforcement,
    JSON extraction, data validation, and graceful keyless fallbacks.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'ANTHROPIC_API_KEY', '') or os.environ.get('ANTHROPIC_API_KEY', '')
        self.model = model or getattr(settings, 'ANTHROPIC_MODEL', 'claude-3-5-sonnet-20241022')
        self._client = None

    def is_configured(self) -> bool:
        """Returns True only if a valid-looking API key is configured."""
        return bool(self.api_key and len(self.api_key.strip()) > 10 and self.api_key.strip() != 'your_anthropic_api_key_here')

    def get_client(self):
        """Lazy client initializer."""
        if not ANTHROPIC_AVAILABLE:
            raise RuntimeError("Anthropic SDK is not installed.")
        if not self.is_configured():
            raise ValueError("AI features require Anthropic API configuration.")
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    # =========================================================================
    # FEATURE 1: RECEIPT SCANNING
    # =========================================================================

    def scan_receipt(self, image_bytes: bytes, content_type: str = "image/jpeg") -> Dict[str, Any]:
        """
        Extract structured receipt data using Claude Vision.
        Returns a validated dict with keys: vendor, date, total, tax, currency, category, items.
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "AI features require Anthropic API configuration.",
                "needs_api_key": True
            }

        valid_media_types = ["image/jpeg", "image/png", "image/webp", "image/gif"]
        if content_type not in valid_media_types:
            return {
                "success": False,
                "error": f"Unsupported media type: {content_type}. Use JPEG, PNG, WEBP, or GIF."
            }

        try:
            client = self.get_client()
            b64_image = base64.b64encode(image_bytes).decode("utf-8")

            prompt = (
                "You are an expert receipt OCR and financial auditor. "
                "Analyze this receipt image and extract structured data. "
                "Respond ONLY with a valid JSON object with the following exact keys:\n"
                "{\n"
                '  "vendor": "Name of the merchant or store",\n'
                '  "date": "YYYY-MM-DD (or current date if not visible)",\n'
                '  "total": 0.00 (numeric total amount paid),\n'
                '  "tax": 0.00 (numeric tax amount if listed, else 0.0),\n'
                '  "currency": "INR",\n'
                '  "category": "One of: Food & Dining, Groceries, Transportation, Housing & Utilities, Entertainment, Shopping, Healthcare, Travel, Education, Personal Care, Bills & Services, Other",\n'
                '  "items": [{"name": "item name", "price": 0.00}]\n'
                "}\n"
                "Do NOT include markdown formatting, backticks, or explanatory text. Return raw JSON."
            )

            message = client.messages.create(
                model=self.model,
                max_tokens=800,
                temperature=0.0,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": content_type,
                                    "data": b64_image,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ],
                    }
                ],
            )

            response_text = message.content[0].text
            parsed_data = self._clean_and_parse_json(response_text)
            validated_data = self._validate_receipt_data(parsed_data)

            return {
                "success": True,
                "data": validated_data
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Receipt scanning failed: {str(e)}"
            }

    # =========================================================================
    # FEATURE 2: FINANCIAL INSIGHTS
    # =========================================================================

    def generate_financial_insights(self, financial_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate actionable financial advice and pattern observations from aggregated data.
        Does not send raw individual records or sensitive bank accounts.
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "AI features require Anthropic API configuration.",
                "needs_api_key": True
            }

        try:
            client = self.get_client()

            prompt = (
                "You are an objective, encouraging personal finance analyst. "
                "Review the following verified financial statistics for this user:\n\n"
                f"{json.dumps(financial_snapshot, indent=2)}\n\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. Provide 3 to 4 concise, high-value insights or recommendations.\n"
                "2. Base ALL comments STRICTLY on the numbers provided above. DO NOT invent, assume, or fabricate any numbers.\n"
                "3. If spending increased or exceeded budget, gently identify which category drove the change.\n"
                "4. Return ONLY a valid JSON list of strings, e.g. [\"Insight 1\", \"Insight 2\", \"Insight 3\"].\n"
                "Do not include markdown codeblocks or extra text."
            )

            message = client.messages.create(
                model=self.model,
                max_tokens=600,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text
            insights = self._clean_and_parse_json(response_text)

            if isinstance(insights, dict) and "insights" in insights:
                insights = insights["insights"]

            if not isinstance(insights, list):
                insights = [str(insights)]

            cleaned_insights = [str(item).strip() for item in insights if item]

            return {
                "success": True,
                "insights": cleaned_insights
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to generate financial insights: {str(e)}"
            }

    # =========================================================================
    # FEATURE 3: NATURAL LANGUAGE QUESTIONS ("ASK AI")
    # =========================================================================

    def answer_financial_query(self, query: str, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Answers a user's natural language question using verified backend context data.
        Claude NEVER runs arbitrary SQL. All context is pre-computed by controlled Django queries.
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "AI features require Anthropic API configuration.",
                "needs_api_key": True
            }

        if not query or len(query.strip()) < 3:
            return {
                "success": False,
                "error": "Please enter a valid financial question."
            }

        try:
            client = self.get_client()

            system_instruction = (
                "You are FinTrack Assistant, an intelligent financial advisor. "
                "You answer the user's questions about their expenses, budget, and spending patterns. "
                "Rules:\n"
                "- Answer using ONLY the verified financial facts provided in the context.\n"
                "- If the context does not contain enough data to answer, honestly say so.\n"
                "- NEVER fabricate financial numbers.\n"
                "- Keep responses concise, clear, and actionable (2-4 sentences max).\n"
                "- Use ₹ (INR) or the user's currency symbol when discussing amounts."
            )

            prompt = (
                f"VERIFIED FINANCIAL CONTEXT:\n{json.dumps(context_data, indent=2)}\n\n"
                f"USER QUESTION: {query.strip()}"
            )

            message = client.messages.create(
                model=self.model,
                max_tokens=400,
                temperature=0.1,
                system=system_instruction,
                messages=[{"role": "user", "content": prompt}]
            )

            answer = message.content[0].text.strip()

            return {
                "success": True,
                "answer": answer
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to answer question: {str(e)}"
            }

    # =========================================================================
    # INTERNAL HELPERS & VALIDATION
    # =========================================================================

    def _clean_and_parse_json(self, raw_text: str) -> Any:
        """Strips backticks or code fencing and parses JSON safely."""
        text = raw_text.strip()
        # Remove markdown codeblocks ```json ... ```
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
            text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try finding the first '{' and matching '}' or '[' and ']'
            obj_match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
            if obj_match:
                return json.loads(obj_match.group(1))
            raise ValueError(f"Model output could not be parsed as valid JSON: {text[:100]}...")

    def _validate_receipt_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validates and coerces extracted receipt fields to match application requirements."""
        if not isinstance(data, dict):
            raise ValueError("Receipt data must be a JSON dictionary.")

        # Vendor
        vendor = str(data.get("vendor", "")).strip() or "Unknown Merchant"

        # Date validation
        raw_date = str(data.get("date", "")).strip()
        parsed_date = date.today().isoformat()
        if raw_date:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
                try:
                    parsed_date = datetime.strptime(raw_date, fmt).date().isoformat()
                    break
                except ValueError:
                    continue

        # Total amount validation
        raw_total = data.get("total", 0.0)
        try:
            clean_total = float(str(raw_total).replace(",", "").replace("₹", "").replace("$", "").strip() or 0)
            if clean_total < 0:
                clean_total = 0.0
        except (ValueError, TypeError):
            clean_total = 0.0

        # Tax
        raw_tax = data.get("tax", 0.0)
        try:
            clean_tax = float(str(raw_tax).replace(",", "").replace("₹", "").replace("$", "").strip() or 0)
        except (ValueError, TypeError):
            clean_tax = 0.0

        # Category normalization
        category = str(data.get("category", "Other")).strip()
        standard_categories = [
            'Food & Dining', 'Groceries', 'Transportation', 'Housing & Utilities',
            'Entertainment', 'Shopping', 'Healthcare', 'Travel', 'Education',
            'Personal Care', 'Bills & Services', 'Other'
        ]
        matched_cat = next((c for c in standard_categories if c.lower() in category.lower()), "Other")

        # Currency
        currency = str(data.get("currency", "₹")).strip() or "₹"

        # Line items
        items = data.get("items", [])
        if not isinstance(items, list):
            items = []

        return {
            "vendor": vendor,
            "date": parsed_date,
            "total": round(clean_total, 2),
            "tax": round(clean_tax, 2),
            "currency": currency,
            "category": matched_cat,
            "items": items,
        }
