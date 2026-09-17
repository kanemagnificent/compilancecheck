"""
field_extractor.py
===================
Smart field extraction from raw OCR text.

Uses enhanced regex patterns with contextual extraction for all 7 mandatory
declarations under PCR 2011 Rule 6. Each field is extracted with a confidence
score based on pattern match quality and context.
"""

import re
from typing import Any, Dict, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# FIELD EXTRACTION PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

def extract_all_fields(raw_text: str) -> Dict[str, Dict[str, Any]]:
    """
    Extract all mandatory fields from OCR text.

    Returns dict of {field_key: {value, confidence, source, raw_match}}.
    """
    if not raw_text:
        return _empty_fields()

    fields = {
        "net_quantity": _extract_net_quantity(raw_text),
        "mrp": _extract_mrp(raw_text),
        "manufacturer": _extract_manufacturer(raw_text),
        "mfg_date": _extract_mfg_date(raw_text),
        "best_before": _extract_best_before(raw_text),
        "consumer_care": _extract_consumer_care(raw_text),
        "common_name": _extract_common_name(raw_text),
        "batch_details": _extract_batch_details(raw_text),
        "country_of_origin": _extract_country_of_origin(raw_text),
        "fssai_license": _extract_fssai(raw_text),
    }

    return fields


def _empty_fields() -> Dict[str, Dict[str, Any]]:
    """Return empty field set."""
    keys = [
        "net_quantity", "mrp", "manufacturer", "mfg_date", "best_before",
        "consumer_care", "common_name", "batch_details", "country_of_origin",
        "fssai_license",
    ]
    return {k: {"value": None, "confidence": 0.0, "source": "not_found", "raw_match": None} for k in keys}


# ── Net Quantity (Rule 6(1)(b)) ─────────────────────────────────────────────

def _extract_net_quantity(text: str) -> Dict[str, Any]:
    """
    Extract net quantity declaration.
    Patterns: "NET QUANTITY: 550 g", "Net Wt. 1.5 kg", "Net Content: 200ml", "500 ml"
    """
    patterns = [
        # Explicit label + value
        (re.compile(
            r"(?:NET\s*(?:QUANTITY|QTY|WT|WEIGHT|CONTENT|CONTENTS?))[.:\s]*"
            r"([\d.,]+\s*(?:g|gm|grams?|kg|kilograms?|ml|millilitres?|l|litres?|liters?|cl|pcs|pieces?|nos?|units?))"
            r"(?:\s*(?:/|per)\s*[\d.,]+\s*(?:g|ml|l|pieces?))?",
            re.IGNORECASE,
        ), 1.0),
        # "Contents: 100g"
        (re.compile(
            r"(?:CONTENTS?)[.:\s]+"
            r"([\d.,]+\s*(?:g|gm|kg|ml|l|litres?|pcs|pieces?))",
            re.IGNORECASE,
        ), 0.85),
        # Standalone quantity pattern (less confident)
        (re.compile(
            r"\b([\d.,]+\s*(?:g|gm|kg|ml|l)\b)",
            re.IGNORECASE,
        ), 0.5),
    ]

    for pattern, base_conf in patterns:
        match = pattern.search(text)
        if match:
            value = match.group(0).strip()
            return {
                "value": value,
                "confidence": base_conf,
                "source": "regex",
                "raw_match": match.group(0),
            }

    return {"value": None, "confidence": 0.0, "source": "not_found", "raw_match": None}


# ── MRP (Rule 6(1)(e)) ─────────────────────────────────────────────────────

def _extract_mrp(text: str) -> Dict[str, Any]:
    """
    Extract MRP declaration.
    Patterns: "MRP Rs. 300 (inclusive of all taxes)", "MRP ₹ 150", "M.R.P. Rs 99.50"
    """
    patterns = [
        # Full MRP with "inclusive of all taxes"
        (re.compile(
            r"(?:M(?:aximum|ax\.?)\s*R(?:etail)?\s*P(?:rice)?|MRP|M\.R\.P\.?)[.:\s]*"
            r"(?:Rs\.?|₹|INR)\s*[\d,]+(?:\.\d{1,2})?\s*"
            r"\(?(?:incl(?:usive)?\.?\s*(?:of\s*)?all\s*taxes?)\)?",
            re.IGNORECASE,
        ), 1.0),
        # MRP with amount but maybe missing tax text
        (re.compile(
            r"(?:M(?:aximum|ax\.?)\s*R(?:etail)?\s*P(?:rice)?|MRP|M\.R\.P\.?)[.:\s]*"
            r"(?:Rs\.?|₹|INR)\s*[\d,]+(?:\.\d{1,2})?",
            re.IGNORECASE,
        ), 0.85),
        # MRP followed by number (no Rs/₹ symbol)
        (re.compile(
            r"(?:MRP|M\.R\.P\.?)[.:\s]*(\d{2,5}(?:\.\d{1,2})?)",
            re.IGNORECASE,
        ), 0.7),
        # Just "₹ 300" or "Rs 300" near MRP context
        (re.compile(
            r"(?:Rs\.?|₹)\s*[\d,]+(?:\.\d{1,2})?",
            re.IGNORECASE,
        ), 0.5),
    ]

    for pattern, base_conf in patterns:
        match = pattern.search(text)
        if match:
            value = match.group(0).strip()
            return {
                "value": value,
                "confidence": base_conf,
                "source": "regex",
                "raw_match": match.group(0),
            }

    return {"value": None, "confidence": 0.0, "source": "not_found", "raw_match": None}


# ── Manufacturer / Packer (Rule 6(1)(a)) ────────────────────────────────────

def _extract_manufacturer(text: str) -> Dict[str, Any]:
    """
    Extract manufacturer/packer/importer name and address.
    Patterns: "Mfd by: XYZ Pvt Ltd, City, State", "Manufactured by ABC Corp."
    """
    patterns = [
        # "Mfd by / Manufactured by / Packed by / Marketed by / Imported by"
        (re.compile(
            r"(?:Mf[dg]\.?\s*(?:by|at)|Manufactured\s*(?:by|at|in)|"
            r"Packed\s*(?:by|at)|Packer|Marketed\s*(?:by|for)|"
            r"Imported\s*(?:by|for)|Importer)[.:\s]*"
            r"([^\n]{10,120})",
            re.IGNORECASE,
        ), 0.9),
        # Address with pincode pattern
        (re.compile(
            r"([A-Za-z\s&.,]+(?:Pvt\.?\s*Ltd\.?|Ltd\.?|Inc\.?|Corp\.?|Co\.?|LLP|Industries|Foods|Products))"
            r"[,\s]+([^\n]{10,80}\d{6})",
            re.IGNORECASE,
        ), 0.75),
    ]

    for pattern, base_conf in patterns:
        match = pattern.search(text)
        if match:
            value = match.group(0).strip()
            # Clean up trailing junk
            value = re.sub(r"\s{2,}", " ", value)
            return {
                "value": value[:200],  # Cap length
                "confidence": base_conf,
                "source": "regex",
                "raw_match": match.group(0),
            }

    return {"value": None, "confidence": 0.0, "source": "not_found", "raw_match": None}


# ── Manufacturing Date (Rule 6(1)(d)) ──────────────────────────────────────

def _extract_mfg_date(text: str) -> Dict[str, Any]:
    """
    Extract manufacturing/packing date.
    Patterns: "Mfg Date: 28/MAR/26", "MFD: 03/2025", "Packed on: Jan 2025"
    """
    patterns = [
        # Labeled date: "Mfg Date: DD/MMM/YY"
        (re.compile(
            r"(?:Mf[dg]\.?\s*(?:Date|Dt\.?)?|Date\s*of\s*(?:Manufacture|Manufacturing|Mfg|Packing|Pkg|Import))"
            r"[.:\s]*(\d{1,2}[\s/\-\.]\w{3,9}[\s/\-\.]\d{2,4})",
            re.IGNORECASE,
        ), 0.95),
        # "MFD: MM/YYYY" or "MFD: MM-YYYY"
        (re.compile(
            r"(?:Mf[dg]\.?\s*(?:Date|Dt\.?)?|Pkg\.?\s*(?:Date|Dt\.?))"
            r"[.:\s]*(\d{1,2}[\s/\-\.]\d{2,4})",
            re.IGNORECASE,
        ), 0.85),
        # "MFD: MMM YYYY" or "MFD: January 2025"
        (re.compile(
            r"(?:Mf[dg]\.?\s*(?:Date|Dt\.?)?)"
            r"[.:\s]*([A-Za-z]{3,9}[\s/\-\.]\d{2,4})",
            re.IGNORECASE,
        ), 0.85),
        # Standalone date pattern DD/MM/YYYY
        (re.compile(r"\b(\d{2}/\d{2}/\d{2,4})\b"), 0.5),
        # DD/MMM/YY
        (re.compile(r"\b(\d{2}/[A-Z]{3}/\d{2,4})\b"), 0.6),
    ]

    for pattern, base_conf in patterns:
        match = pattern.search(text)
        if match:
            value = match.group(0).strip()
            return {
                "value": value,
                "confidence": base_conf,
                "source": "regex",
                "raw_match": match.group(0),
            }

    return {"value": None, "confidence": 0.0, "source": "not_found", "raw_match": None}


# ── Best Before / Use By (Rule 6(1)(f)) ────────────────────────────────────

def _extract_best_before(text: str) -> Dict[str, Any]:
    """
    Extract best before / use by / expiry date.
    Patterns: "Best Before: 12 months", "Use By: 15/06/2026", "Exp: 03/2026"
    """
    patterns = [
        # "Best Before X months/days from manufacture"
        (re.compile(
            r"(?:Best\s*Before|Best\s*By|Use\s*(?:By|Before))[.:\s]*"
            r"(\d{1,3}\s*(?:months?|days?|years?)\s*(?:from\s*(?:manufacture|mfg|packing|pkg|date\s*of\s*manufacture))?)",
            re.IGNORECASE,
        ), 0.9),
        # "Best Before: DD/MM/YYYY"
        (re.compile(
            r"(?:Best\s*Before|Best\s*By|Use\s*(?:By|Before)|Expiry|Exp\.?\s*(?:Date|Dt\.?)?)"
            r"[.:\s]*(\d{1,2}[\s/\-\.]\w{2,9}[\s/\-\.]\d{2,4})",
            re.IGNORECASE,
        ), 0.95),
        # "Exp: MM/YYYY"
        (re.compile(
            r"(?:Expiry|Exp\.?\s*(?:Date|Dt\.?)?|Best\s*Before)"
            r"[.:\s]*(\d{1,2}[\s/\-\.]\d{2,4})",
            re.IGNORECASE,
        ), 0.85),
        # "Exp: MMM YYYY"
        (re.compile(
            r"(?:Expiry|Exp\.?\s*(?:Date|Dt\.?)?|Best\s*Before)"
            r"[.:\s]*([A-Za-z]{3,9}[\s/\-\.]\d{2,4})",
            re.IGNORECASE,
        ), 0.85),
    ]

    for pattern, base_conf in patterns:
        match = pattern.search(text)
        if match:
            value = match.group(0).strip()
            return {
                "value": value,
                "confidence": base_conf,
                "source": "regex",
                "raw_match": match.group(0),
            }

    return {"value": None, "confidence": 0.0, "source": "not_found", "raw_match": None}


# ── Consumer Care (Rule 6(1)(g)) ────────────────────────────────────────────

def _extract_consumer_care(text: str) -> Dict[str, Any]:
    """
    Extract consumer care / customer care details.
    Patterns: phone numbers, email addresses, helpline numbers.
    """
    patterns = [
        # Labeled consumer care with phone/email
        (re.compile(
            r"(?:Customer|Consumer)\s*(?:Care|Service|Helpline|Support)[.:\s]*"
            r"([^\n]{10,150})",
            re.IGNORECASE,
        ), 0.9),
        # Toll-free number
        (re.compile(
            r"(?:Toll\s*Free|Helpline|Contact\s*(?:Us|No\.?))[.:\s]*"
            r"([\d\s\-+()]{8,20})",
            re.IGNORECASE,
        ), 0.85),
        # Standalone phone number (10+ digits)
        (re.compile(r"\b(\d{10,12})\b"), 0.4),
        # Email address
        (re.compile(r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})"), 0.6),
    ]

    for pattern, base_conf in patterns:
        match = pattern.search(text)
        if match:
            value = match.group(0).strip()
            return {
                "value": value[:200],
                "confidence": base_conf,
                "source": "regex",
                "raw_match": match.group(0),
            }

    return {"value": None, "confidence": 0.0, "source": "not_found", "raw_match": None}


# ── Common / Generic Name (Rule 6(1)(c)) ───────────────────────────────────

def _extract_common_name(text: str) -> Dict[str, Any]:
    """
    Extract common/generic name of the commodity.
    This is the hardest field — it's usually the product title at the top.
    """
    patterns = [
        # Explicit product type keywords
        (re.compile(
            r"([A-Za-z\s]+(?:FLAVOU?RED\s*)?(?:ICE\s*CREAM|BISCUITS?|COOKIES?|CHIPS?|"
            r"CHOCOLATE|CANDY|NOODLES?|PASTA|RICE|FLOUR|ATTA|OIL|TEA|COFFEE|JUICE|"
            r"MILK|WATER|SOAP|SHAMPOO|DETERGENT|TOOTHPASTE|CREAM|POWDER|SAUCE|"
            r"KETCHUP|JAM|PICKLE|CEREAL|SUGAR|SALT|HONEY|BREAD|GHEE|BUTTER|"
            r"PANEER|CHEESE|YOGURT|CURD))",
            re.IGNORECASE,
        ), 0.85),
        # After "Product:" or "Name:" label
        (re.compile(
            r"(?:Product|Name|Item)[.:\s]+([A-Za-z\s]{3,50})",
            re.IGNORECASE,
        ), 0.75),
    ]

    for pattern, base_conf in patterns:
        match = pattern.search(text)
        if match:
            value = match.group(0).strip()
            if len(value) > 3:
                return {
                    "value": value[:100],
                    "confidence": base_conf,
                    "source": "regex",
                    "raw_match": match.group(0),
                }

    return {"value": None, "confidence": 0.0, "source": "not_found", "raw_match": None}


# ── Batch / Lot Details ─────────────────────────────────────────────────────

def _extract_batch_details(text: str) -> Dict[str, Any]:
    """Extract batch number / lot number."""
    patterns = [
        (re.compile(
            r"(?:Batch|Lot)\s*(?:No\.?|Number|#)?[.:\s]*([A-Z0-9\-]{4,20})",
            re.IGNORECASE,
        ), 0.9),
        # Standalone alphanumeric code (fallback)
        (re.compile(r"\b([A-Z]{2,4}\d{4,12}[A-Z0-9]*)\b"), 0.6),
    ]

    for pattern, base_conf in patterns:
        match = pattern.search(text)
        if match:
            value = match.group(0).strip()
            # Exclude common false positives
            if not re.match(r"^(FSSAI|MRP|NET|GST|ISBN)", value, re.IGNORECASE):
                return {
                    "value": value,
                    "confidence": base_conf,
                    "source": "regex",
                    "raw_match": match.group(0),
                }

    return {"value": None, "confidence": 0.0, "source": "not_found", "raw_match": None}


# ── Country of Origin (Rule 6(1)(h)) ───────────────────────────────────────

def _extract_country_of_origin(text: str) -> Dict[str, Any]:
    """Extract country of origin for imported goods."""
    patterns = [
        (re.compile(
            r"(?:Country\s*of\s*Origin|Made\s*in|Product\s*of|Origin|Imported\s*from)"
            r"[.:\s]*([A-Za-z\s]{3,30})",
            re.IGNORECASE,
        ), 0.9),
    ]

    for pattern, base_conf in patterns:
        match = pattern.search(text)
        if match:
            value = match.group(0).strip()
            return {
                "value": value,
                "confidence": base_conf,
                "source": "regex",
                "raw_match": match.group(0),
            }

    return {"value": None, "confidence": 0.0, "source": "not_found", "raw_match": None}


# ── FSSAI License Number ───────────────────────────────────────────────────

def _extract_fssai(text: str) -> Dict[str, Any]:
    """Extract FSSAI license number (14-digit number)."""
    patterns = [
        (re.compile(
            r"(?:FSSAI|Lic\.?\s*No\.?|License\s*No\.?|Reg\.?\s*No\.?)"
            r"[.:\s]*(\d{14})",
            re.IGNORECASE,
        ), 0.95),
        # Standalone 14-digit number near FSSAI context
        (re.compile(r"\b(\d{14})\b"), 0.5),
    ]

    for pattern, base_conf in patterns:
        match = pattern.search(text)
        if match:
            value = match.group(0).strip()
            return {
                "value": value,
                "confidence": base_conf,
                "source": "regex",
                "raw_match": match.group(0),
            }

    return {"value": None, "confidence": 0.0, "source": "not_found", "raw_match": None}
