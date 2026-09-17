"""
product_classifier.py
======================
Product category classification for Legal Metrology compliance.

Classifies products into categories based on extracted text and keywords.
Used to determine which rules apply (e.g., food items need best-before dates,
imports need country-of-origin).

Categories aligned with Second Schedule of PCR 2011.
"""

import re
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCT CATEGORIES (aligned with PCR 2011 Second Schedule)
# ═══════════════════════════════════════════════════════════════════════════════

PRODUCT_CATEGORIES = {
    "food_beverages": {
        "label": "Food & Beverages",
        "icon": "🍽️",
        "requires_best_before": True,
        "requires_fssai": True,
        "keywords": [
            "biscuit", "cookie", "chips", "snack", "wafer", "namkeen",
            "chocolate", "candy", "sweet", "toffee", "lollipop",
            "cereal", "oats", "muesli", "cornflakes",
            "rice", "wheat", "flour", "atta", "maida", "suji", "rava",
            "dal", "pulse", "lentil", "chana", "moong", "toor", "urad",
            "tea", "coffee", "cocoa",
            "milk", "dairy", "curd", "yogurt", "paneer", "cheese", "butter", "ghee",
            "juice", "drink", "beverage", "soda", "cola", "water",
            "oil", "cooking oil", "mustard oil", "sunflower oil", "olive oil",
            "sugar", "jaggery", "honey",
            "spice", "masala", "turmeric", "chilli", "pepper", "cumin",
            "sauce", "ketchup", "mayonnaise", "pickle", "chutney", "jam",
            "noodle", "pasta", "macaroni", "vermicelli",
            "bread", "rusk", "cake", "pastry",
            "ice cream", "frozen", "kulfi",
            "baby food", "infant formula",
            "meat", "chicken", "fish", "egg", "seafood",
            "ingredients", "food", "edible", "eat", "consume",
        ],
        "second_schedule": True,
    },
    "personal_care": {
        "label": "Personal Care & Cosmetics",
        "icon": "🧴",
        "requires_best_before": True,
        "requires_fssai": False,
        "keywords": [
            "soap", "shampoo", "conditioner", "body wash", "face wash",
            "cream", "lotion", "moisturizer", "sunscreen", "serum",
            "toothpaste", "dental", "mouthwash",
            "deodorant", "perfume", "fragrance", "cologne",
            "hair oil", "hair color", "hair dye", "gel",
            "cosmetic", "makeup", "lipstick", "foundation", "mascara",
            "talcum", "powder", "face powder",
            "razor", "shaving",
            "sanitary", "diaper", "napkin", "pad",
            "tissue", "wipe", "cotton",
        ],
        "second_schedule": False,
    },
    "household_cleaning": {
        "label": "Household & Cleaning",
        "icon": "🧹",
        "requires_best_before": False,
        "requires_fssai": False,
        "keywords": [
            "detergent", "washing powder", "fabric softener",
            "dish", "dishwash", "utensil cleaner",
            "floor cleaner", "toilet cleaner", "bathroom cleaner",
            "phenyl", "disinfectant", "sanitizer",
            "air freshener", "room spray",
            "insecticide", "mosquito", "repellent",
            "bleach", "stain remover",
        ],
        "second_schedule": True,
    },
    "pharmaceutical": {
        "label": "Pharmaceuticals & Health",
        "icon": "💊",
        "requires_best_before": True,
        "requires_fssai": False,
        "keywords": [
            "tablet", "capsule", "syrup", "medicine", "drug",
            "ointment", "balm", "gel",
            "supplement", "vitamin", "mineral",
            "protein", "whey", "bcaa",
            "ayurvedic", "homeopathic", "herbal",
            "bandage", "gauze", "plaster",
        ],
        "second_schedule": False,
    },
    "industrial_construction": {
        "label": "Industrial & Construction",
        "icon": "🏗️",
        "requires_best_before": False,
        "requires_fssai": False,
        "keywords": [
            "cement", "paint", "varnish", "lacquer",
            "adhesive", "glue", "sealant",
            "lubricant", "grease", "motor oil",
            "battery", "bulb", "wire", "cable",
            "nut", "bolt", "screw", "nail",
            "pipe", "fitting",
        ],
        "second_schedule": True,
    },
    "electronics": {
        "label": "Electronics & Appliances",
        "icon": "📱",
        "requires_best_before": False,
        "requires_fssai": False,
        "keywords": [
            "charger", "adapter", "earphone", "headphone",
            "speaker", "power bank", "usb", "cable",
            "led", "lamp", "fan", "heater",
            "iron", "mixer", "grinder", "blender",
            "television", "remote", "controller",
        ],
        "second_schedule": False,
    },
    "clothing_textiles": {
        "label": "Clothing & Textiles",
        "icon": "👕",
        "requires_best_before": False,
        "requires_fssai": False,
        "keywords": [
            "shirt", "pant", "jeans", "trouser",
            "saree", "kurta", "dupatta",
            "undergarment", "socks", "hosiery",
            "fabric", "cloth", "cotton", "polyester", "silk",
            "towel", "bedsheet", "pillow", "blanket",
        ],
        "second_schedule": False,
    },
    "stationery": {
        "label": "Stationery & Office",
        "icon": "✏️",
        "requires_best_before": False,
        "requires_fssai": False,
        "keywords": [
            "pen", "pencil", "eraser", "sharpener",
            "notebook", "register", "paper", "envelope",
            "stapler", "tape", "scissors", "ruler",
            "ink", "marker", "highlighter",
            "file", "folder", "binder",
        ],
        "second_schedule": False,
    },
}


def classify_product(raw_text: str, extracted_fields: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Classify a product into a Legal Metrology category based on OCR text.

    Returns the best matching category with confidence and applicable rules.
    """
    if not raw_text:
        return _default_classification()

    text_lower = raw_text.lower()
    scores = {}

    for cat_key, cat_info in PRODUCT_CATEGORIES.items():
        score = 0
        matched_keywords = []
        for kw in cat_info["keywords"]:
            if kw in text_lower:
                # Longer keywords are more specific → higher weight
                weight = len(kw.split())
                score += weight
                matched_keywords.append(kw)

        if score > 0:
            scores[cat_key] = {
                "score": score,
                "matched_keywords": matched_keywords[:5],  # Top 5
            }

    if not scores:
        return _default_classification()

    # Sort by score descending
    ranked = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
    best_key = ranked[0][0]
    best_info = PRODUCT_CATEGORIES[best_key]
    best_score = ranked[0][1]["score"]

    # Confidence: normalized by max possible score for the category
    max_possible = len(best_info["keywords"])
    confidence = min(1.0, best_score / max(1, max_possible) * 5)  # Scale up

    return {
        "category": best_key,
        "label": best_info["label"],
        "icon": best_info["icon"],
        "confidence": round(confidence, 2),
        "matched_keywords": ranked[0][1]["matched_keywords"],
        "requires_best_before": best_info["requires_best_before"],
        "requires_fssai": best_info["requires_fssai"],
        "second_schedule": best_info["second_schedule"],
        "alternatives": [
            {"category": k, "label": PRODUCT_CATEGORIES[k]["label"], "score": v["score"]}
            for k, v in ranked[1:3]
        ],
    }


def _default_classification() -> Dict[str, Any]:
    """Return a default/unknown classification."""
    return {
        "category": "unknown",
        "label": "General / Unclassified",
        "icon": "📦",
        "confidence": 0.0,
        "matched_keywords": [],
        "requires_best_before": False,
        "requires_fssai": False,
        "second_schedule": False,
        "alternatives": [],
    }


def get_all_categories() -> List[Dict[str, str]]:
    """Return all product categories for UI display."""
    return [
        {"key": k, "label": v["label"], "icon": v["icon"]}
        for k, v in PRODUCT_CATEGORIES.items()
    ]
