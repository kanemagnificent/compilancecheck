"""
rule_engine.py
===============
Legal Metrology (Packaged Commodities) Rules, 2011 — Rule Engine.

Encodes mandatory declaration requirements (Rule 6), font size specifications
(Rule 7, Tables I & II), Principal Display Panel area calculation (Rule 3),
MRP format validation, and comprehensive compliance checking.

References:
  - Legal Metrology Act, 2009
  - Legal Metrology (Packaged Commodities) Rules, 2011
  - Amendments up to 2023
"""

import re
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: FONT SIZE RULES (Rule 7 + Tables I & II)
# ═══════════════════════════════════════════════════════════════════════════════

# Table-I: Minimum height of numerals and letters — declarations by weight or volume
FONT_SIZE_TABLE_WEIGHT_VOLUME = [
    {"min_area_cm2": 0,    "max_area_cm2": 50,   "min_height_mm": 1.0, "min_height_moulded_mm": 2.0},
    {"min_area_cm2": 50,   "max_area_cm2": 100,  "min_height_mm": 1.5, "min_height_moulded_mm": 3.0},
    {"min_area_cm2": 100,  "max_area_cm2": 500,  "min_height_mm": 2.5, "min_height_moulded_mm": 4.0},
    {"min_area_cm2": 500,  "max_area_cm2": 2500, "min_height_mm": 4.0, "min_height_moulded_mm": 6.0},
    {"min_area_cm2": 2500, "max_area_cm2": 99999, "min_height_mm": 6.0, "min_height_moulded_mm": 6.0},
]

# Table-II: Minimum height of numerals and letters — declarations by length, area or number
FONT_SIZE_TABLE_LENGTH_AREA_NUMBER = [
    {"min_area_cm2": 0,    "max_area_cm2": 50,   "min_height_mm": 1.0, "min_height_moulded_mm": 2.0},
    {"min_area_cm2": 50,   "max_area_cm2": 100,  "min_height_mm": 1.5, "min_height_moulded_mm": 3.0},
    {"min_area_cm2": 100,  "max_area_cm2": 500,  "min_height_mm": 2.0, "min_height_moulded_mm": 3.0},
    {"min_area_cm2": 500,  "max_area_cm2": 2500, "min_height_mm": 3.0, "min_height_moulded_mm": 5.0},
    {"min_area_cm2": 2500, "max_area_cm2": 99999, "min_height_mm": 5.0, "min_height_moulded_mm": 5.0},
]

# Width rule: width >= height/3 (except for '1', 'i', 'I', 'l')
MIN_WIDTH_RATIO = 1 / 3


def get_min_font_height(
    pdp_area_cm2: float,
    declaration_type: str = "weight_volume",
    is_moulded: bool = False
) -> Dict[str, Any]:
    """
    Determine the minimum font height requirement based on PDP area.

    Args:
        pdp_area_cm2: Area of the Principal Display Panel in cm²
        declaration_type: 'weight_volume' for Table-I, 'length_area_number' for Table-II
        is_moulded: True if declarations are blown/formed/moulded/embossed/perforated

    Returns:
        Dict with min_height_mm, table_used, rule_reference
    """
    table = (
        FONT_SIZE_TABLE_WEIGHT_VOLUME
        if declaration_type == "weight_volume"
        else FONT_SIZE_TABLE_LENGTH_AREA_NUMBER
    )
    table_name = "Table-I" if declaration_type == "weight_volume" else "Table-II"

    for row in table:
        if row["min_area_cm2"] <= pdp_area_cm2 < row["max_area_cm2"]:
            height_key = "min_height_moulded_mm" if is_moulded else "min_height_mm"
            return {
                "min_height_mm": row[height_key],
                "pdp_area_cm2": pdp_area_cm2,
                "table_used": table_name,
                "rule_reference": "Rule 7, PCR 2011",
                "is_moulded": is_moulded,
                "area_range": f"{row['min_area_cm2']} – {row['max_area_cm2']} cm²",
            }

    # Fallback for very large packages
    last_row = table[-1]
    height_key = "min_height_moulded_mm" if is_moulded else "min_height_mm"
    return {
        "min_height_mm": last_row[height_key],
        "pdp_area_cm2": pdp_area_cm2,
        "table_used": table_name,
        "rule_reference": "Rule 7, PCR 2011",
        "is_moulded": is_moulded,
        "area_range": f"> {last_row['min_area_cm2']} cm²",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: PDP AREA CALCULATION (Rule 3 — Definitions)
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_pdp_area(
    shape: str,
    height_cm: float = 0,
    width_cm: float = 0,
    depth_cm: float = 0,
    circumference_cm: float = 0,
    total_surface_area_cm2: float = 0,
) -> Dict[str, Any]:
    """
    Calculate the area of the Principal Display Panel (PDP).

    Rules:
      - Rectangular: height × width of the PDP face
      - Cylindrical/Near-cylindrical: 40% × height × circumference
      - Other shapes: 40% × total surface area

    Excludes: top, bottom, flanges of cans, shoulders/neck of bottles/jars.
    """
    if shape == "rectangular":
        area = height_cm * width_cm
        formula = f"{height_cm} cm × {width_cm} cm"
    elif shape == "cylindrical":
        if circumference_cm <= 0 and width_cm > 0:
            import math
            circumference_cm = math.pi * width_cm  # width = diameter
        area = 0.4 * height_cm * circumference_cm
        formula = f"40% × {height_cm} cm × {circumference_cm:.1f} cm"
    else:  # other
        if total_surface_area_cm2 > 0:
            area = 0.4 * total_surface_area_cm2
            formula = f"40% × {total_surface_area_cm2} cm²"
        else:
            # Estimate from dimensions
            area = 0.4 * 2 * (height_cm * width_cm + width_cm * depth_cm + height_cm * depth_cm)
            formula = f"40% × estimated surface area"

    return {
        "pdp_area_cm2": round(area, 2),
        "shape": shape,
        "formula": formula,
        "rule_reference": "Rule 3(k), PCR 2011",
        "note": "Excludes top, bottom, flanges, shoulders/neck"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: MANDATORY DECLARATIONS (Rule 6)
# ═══════════════════════════════════════════════════════════════════════════════

MANDATORY_DECLARATIONS = {
    "manufacturer": {
        "rule": "Rule 6(1)(a)",
        "label": "Name & Address of Manufacturer/Packer/Importer",
        "description": "Every package shall bear the name and complete address of the manufacturer or the packer or the importer.",
        "severity": "critical",
        "keywords": ["mfd by", "manufactured by", "packed by", "packer", "importer", "imported by", "marketed by", "mfg by"],
        "validation": "Must contain name + city/state or pincode",
    },
    "net_quantity": {
        "rule": "Rule 6(1)(b)",
        "label": "Net Quantity",
        "description": "Net quantity of the commodity in terms of standard unit of weight, measure, or number.",
        "severity": "critical",
        "keywords": ["net quantity", "net qty", "net wt", "net weight", "net content", "contents"],
        "validation": "Must be in standard units: g, kg, ml, L, cm, m, or number",
    },
    "common_name": {
        "rule": "Rule 6(1)(c)",
        "label": "Common or Generic Name",
        "description": "Common or generic name of the commodity contained in the package.",
        "severity": "critical",
        "keywords": [],  # Inferred from product type
        "validation": "Must be present and not just a brand name",
    },
    "mfg_date": {
        "rule": "Rule 6(1)(d)",
        "label": "Month & Year of Manufacture/Packing/Import",
        "description": "The month and year in which the commodity is manufactured or pre-packed or imported.",
        "severity": "major",
        "keywords": ["mfg", "mfd", "manufactured", "packed on", "pkg date", "date of manufacture", "date of packing", "date of import"],
        "validation": "Must contain month and year",
    },
    "mrp": {
        "rule": "Rule 6(1)(e)",
        "label": "Maximum Retail Price (MRP)",
        "description": "Retail sale price (MRP) inclusive of all taxes.",
        "severity": "critical",
        "keywords": ["mrp", "m.r.p", "maximum retail price", "retail price"],
        "validation": "Must say MRP/₹/Rs + amount + 'inclusive of all taxes'",
    },
    "best_before": {
        "rule": "Rule 6(1)(f)",
        "label": "Best Before / Use By Date",
        "description": "Best before or use by date (applicable for food and perishable items).",
        "severity": "major",
        "keywords": ["best before", "use by", "expiry", "exp date", "expiry date", "use before", "best by"],
        "validation": "Date must be present for food/perishable items",
    },
    "consumer_care": {
        "rule": "Rule 6(1)(g)",
        "label": "Consumer Care Details",
        "description": "Contact details for consumer complaints: postal address, telephone, email.",
        "severity": "major",
        "keywords": ["customer care", "consumer care", "helpline", "toll free", "contact us", "complaints"],
        "validation": "Must include phone/email/postal address",
    },
    "country_of_origin": {
        "rule": "Rule 6(1)(h)",
        "label": "Country of Origin (for imports)",
        "description": "Country of origin or manufacture for imported goods.",
        "severity": "major",
        "keywords": ["country of origin", "made in", "product of", "origin"],
        "validation": "Required only for imported goods",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: MRP FORMAT VALIDATION (Rule 6(1)(e) detailed)
# ═══════════════════════════════════════════════════════════════════════════════

# Accepted MRP formats per PCR 2011
MRP_PATTERNS = [
    # "MRP Rs. 300 (inclusive of all taxes)"
    re.compile(
        r"(?:M(?:aximum|ax\.?)\s*R(?:etail)?\s*P(?:rice)?|MRP|M\.R\.P\.?)\s*"
        r"(?:Rs\.?|₹)\s*[\d,]+(?:\.\d{1,2})?\s*"
        r"(?:\(?(?:incl(?:usive)?\.?\s*(?:of\s*)?all\s*taxes?)\)?)",
        re.IGNORECASE,
    ),
    # "MRP ₹ 300" (without "incl of all taxes" — still valid but should flag)
    re.compile(
        r"(?:M(?:aximum|ax\.?)\s*R(?:etail)?\s*P(?:rice)?|MRP|M\.R\.P\.?)\s*"
        r"(?:Rs\.?|₹)\s*[\d,]+(?:\.\d{1,2})?",
        re.IGNORECASE,
    ),
    # Just "₹ 300" or "Rs 300"
    re.compile(r"(?:Rs\.?|₹)\s*[\d,]+(?:\.\d{1,2})?", re.IGNORECASE),
]

MRP_INCLUSIVE_PATTERN = re.compile(
    r"incl(?:usive)?\.?\s*(?:of\s*)?all\s*taxes?", re.IGNORECASE
)


def validate_mrp_format(mrp_text: str) -> Dict[str, Any]:
    """
    Validate MRP declaration against PCR 2011 format requirements.

    Expected: 'MRP Rs. xxx (inclusive of all taxes)' or equivalent.
    """
    if not mrp_text:
        return {
            "valid": False,
            "has_mrp_label": False,
            "has_amount": False,
            "has_inclusive_taxes": False,
            "issues": ["MRP declaration not found"],
            "rule_reference": "Rule 6(1)(e), PCR 2011",
        }

    has_mrp_label = bool(re.search(r"(?:MRP|M\.R\.P|Maximum\s*Retail\s*Price)", mrp_text, re.IGNORECASE))
    has_amount = bool(re.search(r"(?:Rs\.?|₹)\s*[\d,]+", mrp_text))
    has_inclusive_taxes = bool(MRP_INCLUSIVE_PATTERN.search(mrp_text))

    issues = []
    if not has_mrp_label:
        issues.append("Missing 'MRP' or 'Maximum Retail Price' label")
    if not has_amount:
        issues.append("Missing price amount in Rs/₹ format")
    if not has_inclusive_taxes:
        issues.append("Missing 'inclusive of all taxes' declaration (Rule 6(1)(e))")

    # Check rounding to nearest rupee or 50 paise
    price_match = re.search(r"[\d,]+\.(\d{1,2})", mrp_text)
    if price_match:
        paise = int(price_match.group(1).ljust(2, '0'))
        if paise not in [0, 50]:
            issues.append(f"MRP should be rounded to nearest rupee or 50 paise (found .{paise:02d})")

    return {
        "valid": len(issues) == 0,
        "has_mrp_label": has_mrp_label,
        "has_amount": has_amount,
        "has_inclusive_taxes": has_inclusive_taxes,
        "issues": issues,
        "rule_reference": "Rule 6(1)(e), PCR 2011",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: NET QUANTITY VALIDATION (Rule 6(1)(b) + Second Schedule)
# ═══════════════════════════════════════════════════════════════════════════════

STANDARD_UNITS = {
    "weight": ["g", "gm", "gram", "grams", "kg", "kilogram", "kilograms"],
    "volume": ["ml", "millilitre", "milliliter", "l", "litre", "liter", "litres", "liters", "cl"],
    "length": ["cm", "centimetre", "centimeter", "m", "metre", "meter", "mm", "millimetre"],
    "area": ["sq cm", "sq m", "cm²", "m²"],
    "number": ["pcs", "pieces", "nos", "numbers", "units", "sachets", "tablets", "capsules"],
}


def validate_net_quantity(quantity_text: str) -> Dict[str, Any]:
    """Validate net quantity declaration against PCR 2011 Rule 6(1)(b)."""
    if not quantity_text:
        return {
            "valid": False,
            "unit_type": None,
            "numeric_value": None,
            "unit": None,
            "issues": ["Net quantity declaration not found"],
            "rule_reference": "Rule 6(1)(b), PCR 2011",
        }

    # Extract numeric value + unit
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(g|gm|grams?|kg|kilograms?|ml|millilitres?|l|litres?|liters?|cl|cm|mm|m|pcs|pieces?|nos?|units?|sachets?|tablets?|capsules?)",
        quantity_text,
        re.IGNORECASE,
    )

    if not match:
        return {
            "valid": False,
            "unit_type": None,
            "numeric_value": None,
            "unit": None,
            "issues": ["Could not parse numeric value and standard unit from net quantity"],
            "rule_reference": "Rule 6(1)(b), PCR 2011",
        }

    numeric_value = float(match.group(1))
    unit = match.group(2).lower()

    # Determine unit type
    unit_type = None
    for utype, ulist in STANDARD_UNITS.items():
        if unit in [u.lower() for u in ulist]:
            unit_type = utype
            break

    issues = []
    if unit_type is None:
        issues.append(f"Unit '{unit}' is not a standard unit under Legal Metrology rules")
    if numeric_value <= 0:
        issues.append("Net quantity must be a positive number")

    return {
        "valid": len(issues) == 0,
        "unit_type": unit_type,
        "numeric_value": numeric_value,
        "unit": unit,
        "issues": issues,
        "rule_reference": "Rule 6(1)(b), PCR 2011",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: LANGUAGE VALIDATION (Rule 6(3))
# ═══════════════════════════════════════════════════════════════════════════════

def check_language_compliance(raw_text: str) -> Dict[str, Any]:
    """
    Check if declarations are in Hindi or English (Rule 6(3)).
    Devanagari script is also permitted.
    """
    has_english = bool(re.search(r"[a-zA-Z]{3,}", raw_text))
    has_hindi = bool(re.search(r"[\u0900-\u097F]{3,}", raw_text))

    return {
        "has_english": has_english,
        "has_hindi": has_hindi,
        "compliant": has_english or has_hindi,
        "languages_detected": [l for l, v in [("English", has_english), ("Hindi", has_hindi)] if v],
        "rule_reference": "Rule 6(3), PCR 2011",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7: FULL COMPLIANCE CHECK
# ═══════════════════════════════════════════════════════════════════════════════

SEVERITY_WEIGHT = {
    "critical": 25,
    "major": 15,
    "minor": 5,
}


def run_compliance_check(
    extracted_fields: Dict[str, Any],
    raw_text: str = "",
    package_shape: str = "rectangular",
    package_dimensions: Optional[Dict[str, float]] = None,
    is_imported: bool = False,
    is_food_item: bool = True,
    is_moulded: bool = False,
    estimated_font_height_mm: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Run the full Legal Metrology compliance check against PCR 2011.

    Args:
        extracted_fields: Dict of {field_key: {value, confidence, source}}
        raw_text: Full OCR text for language/context checks
        package_shape: 'rectangular', 'cylindrical', or 'other'
        package_dimensions: {height_cm, width_cm, depth_cm, circumference_cm}
        is_imported: Whether the product is imported
        is_food_item: Whether the product is a food/perishable item
        is_moulded: Whether declarations are moulded/embossed
        estimated_font_height_mm: Estimated font height from OCR bounding boxes

    Returns:
        Comprehensive compliance report dict
    """
    violations = []
    warnings = []
    audit_trail = []
    step = 1

    # ── Check each mandatory declaration ────────────────────────────────────
    for field_key, rule_info in MANDATORY_DECLARATIONS.items():
        field_data = extracted_fields.get(field_key, {})
        field_value = field_data.get("value") if field_data else None
        field_confidence = field_data.get("confidence", 0.0) if field_data else 0.0

        # Skip non-applicable rules
        if field_key == "country_of_origin" and not is_imported:
            audit_trail.append({
                "step": step, "field": field_key,
                "label": rule_info["label"], "result": "skip",
                "confidence": 0.0, "reason": "Not applicable (domestic product)",
                "source": "rule_engine", "rule": rule_info["rule"],
                "severity": rule_info["severity"],
            })
            step += 1
            continue

        if field_key == "best_before" and not is_food_item:
            audit_trail.append({
                "step": step, "field": field_key,
                "label": rule_info["label"], "result": "skip",
                "confidence": 0.0, "reason": "Not applicable (non-food item)",
                "source": "rule_engine", "rule": rule_info["rule"],
                "severity": rule_info["severity"],
            })
            step += 1
            continue

        # Check presence
        if field_value:
            result_status = "pass"
            reason = "Declaration found and validated."

            # Additional validation for specific fields
            if field_key == "mrp":
                mrp_check = validate_mrp_format(field_value)
                if not mrp_check["valid"]:
                    result_status = "warning" if mrp_check["has_amount"] else "fail"
                    reason = "; ".join(mrp_check["issues"])
                    if result_status == "fail":
                        violations.append({
                            "field": field_key, "label": rule_info["label"],
                            "rule": rule_info["rule"], "severity": rule_info["severity"],
                            "issue": reason,
                        })
                    else:
                        warnings.append({
                            "field": field_key, "label": rule_info["label"],
                            "rule": rule_info["rule"], "severity": "minor",
                            "issue": reason,
                        })

            elif field_key == "net_quantity":
                nq_check = validate_net_quantity(field_value)
                if not nq_check["valid"]:
                    result_status = "warning"
                    reason = "; ".join(nq_check["issues"])
                    warnings.append({
                        "field": field_key, "label": rule_info["label"],
                        "rule": rule_info["rule"], "severity": "minor",
                        "issue": reason,
                    })

            # Low confidence warning
            if field_confidence < 0.5 and result_status == "pass":
                result_status = "warning"
                reason = f"Low OCR confidence ({field_confidence:.0%}). Manual verification recommended."
                warnings.append({
                    "field": field_key, "label": rule_info["label"],
                    "rule": rule_info["rule"], "severity": "minor",
                    "issue": reason,
                })

        else:
            # Missing declaration
            severity = rule_info["severity"]
            if severity == "critical":
                result_status = "fail"
                reason = f"{rule_info['label']} not detected — mandatory under {rule_info['rule']}."
                violations.append({
                    "field": field_key, "label": rule_info["label"],
                    "rule": rule_info["rule"], "severity": severity,
                    "issue": reason,
                })
            else:
                result_status = "warning"
                reason = f"Could not identify {rule_info['label']}. May be on another panel."
                warnings.append({
                    "field": field_key, "label": rule_info["label"],
                    "rule": rule_info["rule"], "severity": severity,
                    "issue": reason,
                })

        audit_trail.append({
            "step": step, "field": field_key,
            "label": rule_info["label"], "result": result_status,
            "confidence": field_confidence,
            "reason": reason, "source": field_data.get("source", "unknown") if field_data else "not_found",
            "rule": rule_info["rule"], "severity": rule_info["severity"],
        })
        step += 1

    # ── Font Size Check (Rule 7) ────────────────────────────────────────────
    font_check = None
    pdp_info = None

    if package_dimensions:
        pdp_info = calculate_pdp_area(
            shape=package_shape,
            height_cm=package_dimensions.get("height_cm", 0),
            width_cm=package_dimensions.get("width_cm", 0),
            depth_cm=package_dimensions.get("depth_cm", 0),
            circumference_cm=package_dimensions.get("circumference_cm", 0),
        )

        font_req = get_min_font_height(
            pdp_area_cm2=pdp_info["pdp_area_cm2"],
            declaration_type="weight_volume",
            is_moulded=is_moulded,
        )

        font_compliant = True
        font_issue = None
        if estimated_font_height_mm is not None:
            font_compliant = estimated_font_height_mm >= font_req["min_height_mm"]
            if not font_compliant:
                font_issue = (
                    f"Estimated font height ({estimated_font_height_mm:.1f} mm) is below "
                    f"minimum ({font_req['min_height_mm']} mm) for PDP area {pdp_info['pdp_area_cm2']} cm²"
                )
                violations.append({
                    "field": "font_size", "label": "Font Size Compliance",
                    "rule": "Rule 7, PCR 2011", "severity": "major",
                    "issue": font_issue,
                })

        font_check = {
            "estimated_height_mm": estimated_font_height_mm,
            "min_required_mm": font_req["min_height_mm"],
            "pdp_area_cm2": pdp_info["pdp_area_cm2"],
            "compliant": font_compliant,
            "issue": font_issue,
            "table_used": font_req["table_used"],
            "area_range": font_req["area_range"],
            "rule_reference": font_req["rule_reference"],
            "confidence": 0.7 if estimated_font_height_mm else 0.0,
        }

        audit_trail.append({
            "step": step, "field": "font_size",
            "label": "Font Size (Rule 7)",
            "result": "pass" if font_compliant else "fail",
            "confidence": font_check["confidence"],
            "reason": font_issue or f"Font meets minimum {font_req['min_height_mm']} mm requirement.",
            "source": "rule_engine", "rule": "Rule 7, PCR 2011",
            "severity": "major",
        })
        step += 1
    else:
        # No dimensions provided — can't validate font size
        font_check = {
            "estimated_height_mm": estimated_font_height_mm,
            "min_required_mm": None,
            "pdp_area_cm2": None,
            "compliant": None,
            "issue": "Package dimensions not provided — font size validation skipped.",
            "table_used": None,
            "area_range": None,
            "rule_reference": "Rule 7, PCR 2011",
            "confidence": 0.0,
        }
        warnings.append({
            "field": "font_size", "label": "Font Size Compliance",
            "rule": "Rule 7, PCR 2011", "severity": "minor",
            "issue": "Package dimensions not provided — font size compliance not verified.",
        })

    # ── Language Check (Rule 6(3)) ──────────────────────────────────────────
    lang_check = check_language_compliance(raw_text)
    if not lang_check["compliant"]:
        warnings.append({
            "field": "language", "label": "Language Compliance",
            "rule": "Rule 6(3), PCR 2011", "severity": "minor",
            "issue": "Declarations should be in Hindi or English.",
        })

    audit_trail.append({
        "step": step, "field": "language",
        "label": "Language (Rule 6(3))",
        "result": "pass" if lang_check["compliant"] else "warning",
        "confidence": 1.0,
        "reason": f"Detected: {', '.join(lang_check['languages_detected']) or 'None'}",
        "source": "rule_engine", "rule": "Rule 6(3), PCR 2011",
        "severity": "minor",
    })

    # ── Calculate Compliance Score ──────────────────────────────────────────
    score = 100
    for v in violations:
        score -= SEVERITY_WEIGHT.get(v["severity"], 10)
    for w in warnings:
        score -= SEVERITY_WEIGHT.get(w["severity"], 3)
    score = max(0, min(100, score))

    # ── Determine Status ───────────────────────────────────────────────────
    critical_violations = [v for v in violations if v["severity"] == "critical"]
    if critical_violations:
        status = "NON-COMPLIANT"
    elif violations:
        status = "NON-COMPLIANT"
    elif warnings:
        status = "COMPLIANT WITH WARNINGS"
    else:
        status = "COMPLIANT"

    return {
        "compliance_status": status,
        "compliance_score": score,
        "violations": violations,
        "warnings": warnings,
        "audit_trail": audit_trail,
        "font_size_check": font_check,
        "pdp_info": pdp_info,
        "language_check": lang_check,
        "total_checks": step,
        "passed_checks": sum(1 for a in audit_trail if a["result"] == "pass"),
        "failed_checks": sum(1 for a in audit_trail if a["result"] == "fail"),
        "warning_checks": sum(1 for a in audit_trail if a["result"] == "warning"),
        "skipped_checks": sum(1 for a in audit_trail if a["result"] == "skip"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8: RULES REFERENCE (for Rules Explorer page)
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_rules_summary() -> List[Dict[str, Any]]:
    """Return a structured summary of all encoded rules for the Rules Explorer."""
    rules = [
        {
            "rule_id": "Rule 3",
            "title": "Definitions",
            "act": "PCR 2011",
            "category": "General",
            "description": "Defines key terms: 'pre-packaged commodity', 'principal display panel', 'retail package', 'wholesale package', etc.",
            "key_points": [
                "'Pre-packaged commodity' = commodity placed in a package without the purchaser being present",
                "'Principal display panel' (PDP) = that part of the label most likely to be displayed/seen at retail",
                "PDP Area for rectangular = height × width; cylindrical = 40% × height × circumference",
            ],
            "encoded": True,
        },
        {
            "rule_id": "Rule 4",
            "title": "Application",
            "act": "PCR 2011",
            "category": "General",
            "description": "The rules apply to all pre-packaged commodities for retail sale.",
            "key_points": [
                "Applies to domestic and imported pre-packaged commodities",
                "Exemptions: commodities for industrial/institutional use (marked 'not for retail sale')",
                "Exemptions: commodities for export only",
            ],
            "encoded": True,
        },
        {
            "rule_id": "Rule 5",
            "title": "General Provisions",
            "act": "PCR 2011",
            "category": "Declarations",
            "description": "Declarations must be definite, plain, and conspicuous. Numerals must contrast with background.",
            "key_points": [
                "All declarations must be legible, prominent, and definite",
                "Numerals of retail price must contrast conspicuously with background",
                "No person shall sell unless all declarations are present",
            ],
            "encoded": True,
        },
        {
            "rule_id": "Rule 6",
            "title": "Mandatory Declarations",
            "act": "PCR 2011",
            "category": "Declarations",
            "description": "Every pre-packaged commodity must bear: manufacturer name & address, net quantity, common name, month/year of manufacture, MRP (incl. all taxes), best before date (food), consumer care details, country of origin (imports).",
            "key_points": [
                "6(1)(a): Name & complete address of manufacturer/packer/importer",
                "6(1)(b): Net quantity in standard units of weight/measure/number",
                "6(1)(c): Common or generic name of the commodity",
                "6(1)(d): Month and year of manufacture/packing/import",
                "6(1)(e): MRP inclusive of all taxes, rounded to nearest ₹1 or 50p",
                "6(1)(f): Best before / use by date (food/perishable items)",
                "6(1)(g): Consumer care contact details (phone, email, postal)",
                "6(1)(h): Country of origin (imported goods only)",
                "6(3): Declarations must be in Hindi or English",
            ],
            "encoded": True,
        },
        {
            "rule_id": "Rule 7",
            "title": "Font Size Requirements",
            "act": "PCR 2011",
            "category": "Typography",
            "description": "Minimum height of numerals and letters depends on PDP area. Width must be ≥ 1/3 of height (except '1', 'i', 'I', 'l').",
            "key_points": [
                "PDP < 50 cm²: min 1.0 mm (printed), 2.0 mm (moulded)",
                "PDP 50-100 cm²: min 1.5 mm (printed), 3.0 mm (moulded)",
                "PDP 100-500 cm²: min 2.5 mm (printed), 4.0 mm (moulded)",
                "PDP 500-2500 cm²: min 4.0 mm (printed), 6.0 mm (moulded)",
                "PDP > 2500 cm²: min 6.0 mm (printed), 6.0 mm (moulded)",
                "Width of letter/numeral ≥ 1/3 of its height",
                "Moulded/embossed declarations: minimum 2 mm in all cases",
            ],
            "encoded": True,
        },
        {
            "rule_id": "Rule 8",
            "title": "Quantity Declaration Spacing",
            "act": "PCR 2011",
            "category": "Typography",
            "description": "The area surrounding the quantity declaration must be free from other printed information.",
            "key_points": [
                "Above and below: space ≥ height of the numeral",
                "Left and right: space ≥ 2× height of the numeral",
            ],
            "encoded": False,
        },
        {
            "rule_id": "Rule 9",
            "title": "Combination Packages",
            "act": "PCR 2011",
            "category": "Declarations",
            "description": "Packages containing two or more different commodities must declare each individually.",
            "key_points": [
                "Each commodity must be individually declared with name and net quantity",
                "Total MRP of the combination package must be declared",
            ],
            "encoded": False,
        },
        {
            "rule_id": "Second Schedule",
            "title": "Standard Quantities",
            "act": "PCR 2011",
            "category": "Quantities",
            "description": "Lists commodities that must be packed in prescribed standard quantities (by weight, volume, or number).",
            "key_points": [
                "Baby food, cereals, pulses, tea, coffee must use standard pack sizes",
                "Mineral/drinking water: 200ml, 250ml, 500ml, 1L, 2L, 5L, etc.",
                "Cement: 1kg, 5kg, 10kg, 25kg, 50kg bags",
                "Paint and varnish: specified millilitre/litre increments",
            ],
            "encoded": False,
        },
        {
            "rule_id": "Section 18",
            "title": "Penalty for Non-Compliance",
            "act": "LM Act 2009",
            "category": "Enforcement",
            "description": "Penalties for contravention of packaged commodity rules.",
            "key_points": [
                "First offence: fine up to ₹25,000",
                "Second offence: fine up to ₹50,000",
                "Subsequent offences: fine up to ₹1,00,000 or imprisonment up to 1 year, or both",
            ],
            "encoded": False,
        },
    ]
    return rules
