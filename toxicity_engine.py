"""
toxicity_engine.py
===================
Ingredient Toxicity / Consumer-Safety Advisory Engine.

Detects and classifies food additives, preservatives, artificial colors,
and other potentially harmful ingredients. Cross-references against
FSSAI regulations and international food safety standards.
"""

import re
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# INGREDIENT RISK DATABASE
# ═══════════════════════════════════════════════════════════════════════════════

INGREDIENT_RISK_DB: List[Dict[str, Any]] = [
    # ── ARTIFICIAL COLORS / DYES ──────────────────────────────────────────
    {"name": "Tartrazine (E102 / Yellow 5)", "aliases": ["tartrazine", "e102", "e-102", "yellow 5", "fd&c yellow no. 5", "ins 102"],
     "risk_level": "moderate", "category": "artificial_color", "banned_in_india": False,
     "reason": "Synthetic azo dye linked to hyperactivity in children and allergic reactions.",
     "regulation": "FSSAI permits with limits; banned in Austria/Norway"},
    {"name": "Sunset Yellow (E110 / Yellow 6)", "aliases": ["sunset yellow", "e110", "e-110", "yellow 6", "ins 110"],
     "risk_level": "moderate", "category": "artificial_color", "banned_in_india": False,
     "reason": "Azo dye associated with hyperactivity and allergic reactions.",
     "regulation": "FSSAI permits with limits"},
    {"name": "Allura Red (E129 / Red 40)", "aliases": ["allura red", "e129", "e-129", "red 40", "ins 129"],
     "risk_level": "moderate", "category": "artificial_color", "banned_in_india": False,
     "reason": "Synthetic red dye linked to hyperactivity in children.",
     "regulation": "FSSAI permits with limits"},
    {"name": "Carmoisine (E122)", "aliases": ["carmoisine", "e122", "e-122", "ins 122", "azorubine"],
     "risk_level": "moderate", "category": "artificial_color", "banned_in_india": False,
     "reason": "Azo dye associated with allergic and hyperactivity reactions.",
     "regulation": "FSSAI permits with limits"},
    {"name": "Erythrosine (E127 / Red 3)", "aliases": ["erythrosine", "e127", "e-127", "red 3", "ins 127"],
     "risk_level": "high", "category": "artificial_color", "banned_in_india": False,
     "reason": "Iodine-containing dye linked to thyroid tumors in animal studies.",
     "regulation": "FSSAI permits with limits; restricted in many countries"},
    {"name": "Rhodamine B", "aliases": ["rhodamine b", "rhodamine-b"],
     "risk_level": "high", "category": "artificial_color", "banned_in_india": True,
     "reason": "Industrial textile dye illegally used in food; prohibited by FSSAI.",
     "regulation": "BANNED under FSSAI regulations"},
    {"name": "Brilliant Blue (E133)", "aliases": ["brilliant blue", "e133", "e-133", "blue 1", "ins 133"],
     "risk_level": "low", "category": "artificial_color", "banned_in_india": False,
     "reason": "Synthetic blue dye; generally considered safe but may cause allergic reactions in sensitive individuals.",
     "regulation": "FSSAI permits with limits"},
    {"name": "Ponceau 4R (E124)", "aliases": ["ponceau 4r", "e124", "e-124", "ins 124"],
     "risk_level": "moderate", "category": "artificial_color", "banned_in_india": False,
     "reason": "Azo dye linked to hyperactivity; banned in US and Norway.",
     "regulation": "FSSAI permits; banned in USA/Norway"},
    {"name": "Fast Green (E143)", "aliases": ["fast green", "e143", "e-143", "green 3", "ins 143"],
     "risk_level": "moderate", "category": "artificial_color", "banned_in_india": False,
     "reason": "Synthetic green dye; limited safety data available.",
     "regulation": "FSSAI permits with limits"},
    {"name": "Metanil Yellow", "aliases": ["metanil yellow"],
     "risk_level": "high", "category": "artificial_color", "banned_in_india": True,
     "reason": "Industrial dye used illegally in turmeric, dal, sweets; highly toxic.",
     "regulation": "BANNED under FSSAI regulations"},
    {"name": "Sudan Red", "aliases": ["sudan red", "sudan i", "sudan ii", "sudan iii", "sudan iv"],
     "risk_level": "high", "category": "artificial_color", "banned_in_india": True,
     "reason": "Industrial dye classified as carcinogen (Group 3 by IARC).",
     "regulation": "BANNED globally in food"},

    # ── PRESERVATIVES ────────────────────────────────────────────────────
    {"name": "Sodium Benzoate (E211)", "aliases": ["sodium benzoate", "e211", "e-211", "ins 211"],
     "risk_level": "moderate", "category": "preservative", "banned_in_india": False,
     "reason": "Can form benzene (a known carcinogen) when combined with vitamin C under heat/light.",
     "regulation": "FSSAI permits up to 750 mg/kg in specified foods"},
    {"name": "Potassium Benzoate (E212)", "aliases": ["potassium benzoate", "e212", "e-212", "ins 212"],
     "risk_level": "moderate", "category": "preservative", "banned_in_india": False,
     "reason": "Benzene-formation risk when combined with ascorbic acid.",
     "regulation": "FSSAI permits with limits"},
    {"name": "Sodium Nitrite (E250)", "aliases": ["sodium nitrite", "e250", "e-250", "ins 250"],
     "risk_level": "high", "category": "preservative", "banned_in_india": False,
     "reason": "Can form nitrosamines (probable carcinogens) during cooking/digestion. Used in processed meats.",
     "regulation": "FSSAI permits up to 200 mg/kg in cured meats"},
    {"name": "Potassium Nitrate (E252)", "aliases": ["potassium nitrate", "e252", "e-252", "saltpetre", "ins 252"],
     "risk_level": "moderate", "category": "preservative", "banned_in_india": False,
     "reason": "Nitrosamine formation risk; used in cured meats and cheeses.",
     "regulation": "FSSAI permits with limits"},
    {"name": "BHA (E320)", "aliases": ["bha", "butylated hydroxyanisole", "e320", "ins 320"],
     "risk_level": "high", "category": "preservative", "banned_in_india": False,
     "reason": "Anticipated human carcinogen and suspected endocrine disruptor (NTP).",
     "regulation": "FSSAI permits up to 200 mg/kg in fats/oils"},
    {"name": "BHT (E321)", "aliases": ["bht", "butylated hydroxytoluene", "e321", "ins 321"],
     "risk_level": "moderate", "category": "preservative", "banned_in_india": False,
     "reason": "Suspected endocrine disruptor; conflicting study results.",
     "regulation": "FSSAI permits up to 200 mg/kg in fats/oils"},
    {"name": "Potassium Sorbate (E202)", "aliases": ["potassium sorbate", "e202", "e-202", "ins 202"],
     "risk_level": "low", "category": "preservative", "banned_in_india": False,
     "reason": "Generally recognized as safe (GRAS); may cause mild skin sensitization.",
     "regulation": "FSSAI permits with limits"},
    {"name": "TBHQ (E319)", "aliases": ["tbhq", "tert-butylhydroquinone", "e319", "ins 319"],
     "risk_level": "moderate", "category": "preservative", "banned_in_india": False,
     "reason": "Potential nausea and tinnitus at high doses; suspected immunotoxicity.",
     "regulation": "FSSAI permits up to 200 mg/kg"},

    # ── SWEETENERS ───────────────────────────────────────────────────────
    {"name": "Aspartame (E951)", "aliases": ["aspartame", "e951", "e-951", "ins 951"],
     "risk_level": "moderate", "category": "sweetener", "banned_in_india": False,
     "reason": "IARC classified as 'possibly carcinogenic' (Group 2B) in 2023. Unsafe for phenylketonuria (PKU) patients.",
     "regulation": "FSSAI permits; WHO ADI 40 mg/kg body weight"},
    {"name": "Sucralose (E955)", "aliases": ["sucralose", "e955", "e-955", "ins 955"],
     "risk_level": "low", "category": "sweetener", "banned_in_india": False,
     "reason": "Generally considered safe; some studies suggest gut microbiome effects.",
     "regulation": "FSSAI permits with limits"},
    {"name": "Saccharin (E954)", "aliases": ["saccharin", "e954", "e-954", "ins 954"],
     "risk_level": "moderate", "category": "sweetener", "banned_in_india": False,
     "reason": "Historical cancer concerns (delisted by NTP in 2000); bitter aftertaste.",
     "regulation": "FSSAI permits with limits"},
    {"name": "Acesulfame K (E950)", "aliases": ["acesulfame k", "acesulfame potassium", "e950", "e-950", "ins 950", "ace-k"],
     "risk_level": "low", "category": "sweetener", "banned_in_india": False,
     "reason": "Generally considered safe; some studies question long-term effects.",
     "regulation": "FSSAI permits with limits"},

    # ── FLAVOR ENHANCERS ─────────────────────────────────────────────────
    {"name": "MSG (E621)", "aliases": ["msg", "monosodium glutamate", "e621", "e-621", "ins 621", "ajinomoto"],
     "risk_level": "low", "category": "flavor_enhancer", "banned_in_india": False,
     "reason": "Generally safe; 'MSG symptom complex' is unconfirmed by controlled studies.",
     "regulation": "FSSAI permits; no specific limit for most foods"},
    {"name": "Artificial Flavoring (unspecified)", "aliases": ["artificial flavour", "artificial flavor", "nature-identical flavoring", "synthetic flavouring", "nature identical flavouring substances"],
     "risk_level": "low", "category": "flavor_enhancer", "banned_in_india": False,
     "reason": "Umbrella term covering synthetic compounds; allergen risks cannot be individually assessed.",
     "regulation": "FSSAI requires declaration but no blanket ban"},

    # ── FATS / OILS ──────────────────────────────────────────────────────
    {"name": "Palm Oil", "aliases": ["palm oil", "fractionated fat", "palm olein", "palmolein"],
     "risk_level": "low", "category": "fat", "banned_in_india": False,
     "reason": "High in saturated fat; environmental concerns (deforestation).",
     "regulation": "FSSAI permits; must be declared on label"},
    {"name": "Partially Hydrogenated Fat/Oil", "aliases": ["partially hydrogenated", "hydrogenated vegetable oil", "hydrogenated fat", "vanaspati"],
     "risk_level": "high", "category": "fat", "banned_in_india": False,
     "reason": "Contains trans fats linked to cardiovascular disease. FSSAI limits trans fat to 2%.",
     "regulation": "FSSAI mandates trans fat ≤ 2% (as of 2022)"},

    # ── STABILIZERS / EMULSIFIERS ────────────────────────────────────────
    {"name": "Caramel Color (E150d)", "aliases": ["color (150d)", "150d", "e150d", "e-150d", "caramel color", "ins 150d"],
     "risk_level": "low", "category": "artificial_color", "banned_in_india": False,
     "reason": "Ammonia-sulfite processed caramel color; contains trace 4-MEI.",
     "regulation": "FSSAI permits with limits"},
    {"name": "Carrageenan (E407)", "aliases": ["carrageenan", "e407", "e-407", "ins 407"],
     "risk_level": "low", "category": "stabilizer", "banned_in_india": False,
     "reason": "Seaweed-derived thickener; some concerns about degraded forms causing GI inflammation.",
     "regulation": "FSSAI permits; banned in infant formula in EU"},
    {"name": "Emulsifiers / Stabilizers (Synthetic)", "aliases": ["471", "477", "410", "412", "322", "440", "476"],
     "risk_level": "low", "category": "stabilizer", "banned_in_india": False,
     "reason": "Common commercial food thickeners and emulsifiers; generally safe in moderation.",
     "regulation": "FSSAI permits with limits"},
    {"name": "Polysorbate 80 (E433)", "aliases": ["polysorbate 80", "e433", "e-433", "ins 433"],
     "risk_level": "moderate", "category": "emulsifier", "banned_in_india": False,
     "reason": "Some animal studies suggest gut microbiome disruption and inflammation.",
     "regulation": "FSSAI permits with limits"},
]

# Build lookup alias list — longer aliases first for greedy matching
_ALIAS_INDEX: List[Dict[str, Any]] = []
for _entry in INGREDIENT_RISK_DB:
    for _alias in _entry["aliases"]:
        _ALIAS_INDEX.append({
            "alias": _alias,
            "pattern": re.compile(r"\b" + re.escape(_alias) + r"\b", re.IGNORECASE),
            "entry": _entry,
        })
_ALIAS_INDEX.sort(key=lambda x: len(x["alias"]), reverse=True)

_RISK_WEIGHT = {"high": 25, "moderate": 15, "low": 5}

# Pattern catches variations: INGREDIENTS:, NGREDIENTS:, CONTAINS, etc.
_INGREDIENTS_HEADER_PATTERN = re.compile(
    r"(?:I?NGREDIENTS?|CONTAINS|COMPOSITION)\s*[:\-]?\s*", re.IGNORECASE
)

_STOP_HEADERS = (
    r"nutritional?\s+(information|facts|value)?",
    r"allergen",
    r"net\s*(wt|weight|qty|quantity)",
    r"mrp|m\.r\.p",
    r"mfg|manufactured|best\s*before|expiry|use\s*by",
    r"storage",
    r"customer|consumer\s*care",
    r"fssai",
    r"batch|lot\s*no",
    r"marketed\s*by",
    r"directions?\s*(for\s*use)?",
    r"caution|warning",
)
_STOP_PATTERN = re.compile(r"(?:" + "|".join(_STOP_HEADERS) + r")", re.IGNORECASE)


def extract_ingredients_section(raw_text: str) -> Optional[str]:
    """Extract the ingredients section from raw OCR text."""
    if not raw_text:
        return None
    header_match = _INGREDIENTS_HEADER_PATTERN.search(raw_text)
    if not header_match:
        return None

    remainder = raw_text[header_match.end():]
    stop_match = _STOP_PATTERN.search(remainder)
    ingredients_text = remainder[: stop_match.start()] if stop_match else remainder
    return ingredients_text.strip(" \n\t.:;-") or None


def split_ingredient_tokens(ingredients_text: str) -> List[str]:
    """Split ingredients text into individual tokens."""
    if not ingredients_text:
        return []
    # Split on commas not inside parentheses
    raw_tokens = re.split(r",(?![^(]*\))", ingredients_text)
    return [t.strip(" \n\t.;") for t in raw_tokens if t.strip()]


def _match_flagged_ingredients(ingredients_text: str) -> List[Dict[str, Any]]:
    """Match ingredients against the risk database."""
    flagged = []
    seen_entry_names = set()
    for record in _ALIAS_INDEX:
        if record["entry"]["name"] in seen_entry_names:
            continue
        match = record["pattern"].search(ingredients_text)
        if match:
            entry = record["entry"]
            flagged.append({
                "name": entry["name"],
                "matched_as": match.group(0),
                "risk_level": entry["risk_level"],
                "category": entry["category"],
                "banned_in_india": entry["banned_in_india"],
                "reason": entry["reason"],
                "regulation": entry.get("regulation", ""),
            })
            seen_entry_names.add(entry["name"])
    return flagged


def compute_verdict(
    toxicity_score: int, high: int, moderate: int, banned_present: bool
) -> Dict[str, str]:
    """Compute the overall safety verdict."""
    if banned_present:
        return {
            "verdict": "NOT RECOMMENDED",
            "verdict_reason": "Contains BANNED ingredient(s) under FSSAI regulations. Immediate action required.",
        }
    if high >= 1 or toxicity_score < 50:
        return {
            "verdict": "NOT RECOMMENDED",
            "verdict_reason": "Contains high-risk ingredients flagged by safety studies.",
        }
    if moderate >= 1 or toxicity_score < 85:
        return {
            "verdict": "USE WITH CAUTION",
            "verdict_reason": f"Contains {moderate} moderate-risk ingredient(s) — best consumed in moderation.",
        }
    return {
        "verdict": "SAFE",
        "verdict_reason": "No high or moderate-risk additives detected.",
    }


def analyze_ingredients(raw_text: str) -> Dict[str, Any]:
    """Analyze ingredients for toxicity risks."""
    ingredients_text = extract_ingredients_section(raw_text)

    if not ingredients_text:
        return {
            "ingredients_raw_text": None,
            "ingredients_list": [],
            "flagged_ingredients": [],
            "safe_ingredients": [],
            "unrecognized_ingredients": [],
            "toxicity_score": 100,
            "verdict": "NO INGREDIENTS DETECTED",
            "verdict_reason": "No 'Ingredients:' section found in the scanned text.",
            "high_risk_count": 0,
            "moderate_risk_count": 0,
            "low_risk_count": 0,
        }

    tokens = split_ingredient_tokens(ingredients_text)
    flagged = _match_flagged_ingredients(ingredients_text)

    high = sum(1 for f in flagged if f["risk_level"] == "high")
    moderate = sum(1 for f in flagged if f["risk_level"] == "moderate")
    low = sum(1 for f in flagged if f["risk_level"] == "low")
    banned_present = any(f["banned_in_india"] for f in flagged)

    score = 100
    for f in flagged:
        score -= _RISK_WEIGHT.get(f["risk_level"], 0)
    toxicity_score = max(30, min(100, score))

    verdict_info = compute_verdict(toxicity_score, high, moderate, banned_present)

    safe_list = [
        t for t in tokens
        if not any(f["matched_as"].lower() in t.lower() for f in flagged)
    ]

    return {
        "ingredients_raw_text": ingredients_text,
        "ingredients_list": tokens,
        "flagged_ingredients": flagged,
        "safe_ingredients": safe_list,
        "unrecognized_ingredients": [],
        "toxicity_score": toxicity_score,
        "verdict": verdict_info["verdict"],
        "verdict_reason": verdict_info["verdict_reason"],
        "high_risk_count": high,
        "moderate_risk_count": moderate,
        "low_risk_count": low,
    }


def run_toxicity_analysis(raw_text: str, enable_ai: bool = True) -> Dict[str, Any]:
    """Public integration entry point."""
    result = analyze_ingredients(raw_text or "")
    result["ai_advisory"] = None
    return result
