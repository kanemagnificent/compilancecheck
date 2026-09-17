"""
ocr_engine.py
==============
Hybrid OCR engine for Pack Proof — Legal Metrology Compliance System.

Combines EasyOCR and Tesseract with advanced image preprocessing,
multi-rotation scanning, and bounding box analysis for font size estimation.
Falls back to demo mode if OCR libraries are not installed.
"""

import os
import re
import math
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

from field_extractor import extract_all_fields
from toxicity_engine import run_toxicity_analysis
from product_classifier import classify_product
from rule_engine import run_compliance_check


# ═══════════════════════════════════════════════════════════════════════════════
# OCR ENGINE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

_EASYOCR_READER = None
HAS_EASYOCR = False
HAS_TESSERACT = False

try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    pass

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    pass


def get_easyocr_reader():
    """Lazy-load the EasyOCR reader (downloads ~1.5GB on first use)."""
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        _EASYOCR_READER = easyocr.Reader(['en'], gpu=False)
    return _EASYOCR_READER


def is_ocr_available() -> bool:
    """Check if any OCR engine is available."""
    return HAS_EASYOCR or HAS_TESSERACT


# ═══════════════════════════════════════════════════════════════════════════════
# IMAGE PREPROCESSING
# ═══════════════════════════════════════════════════════════════════════════════

def preprocess_image(image_path: str) -> Tuple[Any, Any]:
    """
    Advanced image preprocessing pipeline:
    1. Read and validate image
    2. Convert to grayscale
    3. Denoise with Non-Local Means
    4. Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    5. Adaptive thresholding for binarization
    """
    if not HAS_CV2:
        raise ImportError("OpenCV (cv2) is required for image processing")

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image at {image_path}")

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Denoise
    denoised = cv2.fastNlMeansDenoising(gray, h=10)

    # CLAHE for better contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)

    # Adaptive thresholding
    processed = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    return img, processed


def rotate_image(image: Any, angle: int) -> Any:
    """Rotate image by 90° increments."""
    if not HAS_CV2:
        return image
    if angle == 90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    elif angle == 180:
        return cv2.rotate(image, cv2.ROTATE_180)
    elif angle == 270:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return image


# ═══════════════════════════════════════════════════════════════════════════════
# FONT SIZE ESTIMATION
# ═══════════════════════════════════════════════════════════════════════════════

def estimate_font_height_mm(
    text_blocks: List[Dict[str, Any]],
    image_shape: Tuple[int, ...],
    assumed_dpi: float = 300.0,
) -> Optional[float]:
    """
    Estimate the average font height in millimeters from OCR bounding boxes.

    Uses the image DPI (assumed or detected) to convert pixel heights to mm.
    1 inch = 25.4 mm; pixel_height_mm = pixel_height / dpi * 25.4
    """
    if not text_blocks or not image_shape:
        return None

    heights_px = []
    for block in text_blocks:
        bbox = block.get("bbox")
        if bbox is None:
            continue

        # EasyOCR bbox format: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4 and isinstance(bbox[0], (list, tuple)):
            # Get height from bounding box vertices
            ys = [pt[1] for pt in bbox]
            h = max(ys) - min(ys)
            if h > 0:
                heights_px.append(h)
        # Tesseract bbox format: [left, top, width, height]
        elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            h = bbox[3]
            if h > 0:
                heights_px.append(h)

    if not heights_px:
        return None

    # Use median to avoid outliers
    median_height_px = float(sorted(heights_px)[len(heights_px) // 2])

    # Convert to mm: pixels / DPI * 25.4
    mm = median_height_px / assumed_dpi * 25.4

    return round(mm, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# HYBRID OCR ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class HybridOCREngine:
    """
    Multi-engine OCR with rotation scanning and best-result selection.

    Tries EasyOCR first, falls back to Tesseract, merges results.
    """

    def extract(self, image_path: str) -> Dict[str, Any]:
        """Extract text from a single image using the best available OCR engine."""
        if not HAS_CV2:
            raise ImportError("OpenCV required for image processing")

        original_img, processed = preprocess_image(image_path)
        best_blocks, best_conf, best_text = [], 0.0, ""

        # Try multiple rotations to find the best orientation
        for angle in [0, 90, 270, 180]:
            target_img = rotate_image(original_img, angle) if angle != 0 else original_img
            temp_path = None

            if angle != 0:
                temp_path = f"/tmp/packproof_rot_{angle}.jpg"
                cv2.imwrite(temp_path, target_img)
                scan_target = temp_path
            else:
                scan_target = image_path

            try:
                blocks, avg_conf = self._run_ocr(scan_target, target_img)
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)

            raw_text = " ".join([b["text"] for b in blocks])

            # Select the best rotation based on confidence and text length
            if avg_conf > best_conf or len(raw_text) > len(best_text) * 1.5:
                best_conf = avg_conf
                best_blocks = blocks
                best_text = raw_text

            # Early stop if good enough
            if best_conf > 0.6 and len(best_blocks) > 5:
                break

        return {
            "raw_text": best_text,
            "text_blocks": best_blocks,
            "overall_confidence": best_conf,
            "image_shape": original_img.shape,
        }

    def extract_multiple(self, image_paths: Union[List[str], str]) -> Dict[str, Any]:
        """Extract and merge text from multiple images (multi-side scanning)."""
        paths = [p.strip() for p in image_paths.split(",")] if isinstance(image_paths, str) else image_paths
        all_blocks, all_raw_texts, confidences = [], [], []

        for path in paths:
            single_res = self.extract(path)
            if single_res["raw_text"]:
                all_raw_texts.append(single_res["raw_text"])
            all_blocks.extend(single_res["text_blocks"])
            confidences.append(single_res["overall_confidence"])

        return {
            "raw_text": "\n".join(all_raw_texts),
            "text_blocks": all_blocks,
            "overall_confidence": float(np.mean(confidences)) if confidences else 0.0,
            "image_shape": None,
        }

    def _run_ocr(self, image_path: str, image_array: Any = None) -> Tuple[List[Dict], float]:
        """Run OCR using the best available engine."""
        easyocr_blocks, easyocr_conf = [], 0.0
        tess_blocks, tess_conf = [], 0.0

        # Try EasyOCR
        if HAS_EASYOCR:
            try:
                reader = get_easyocr_reader()
                results = reader.readtext(image_path)
                for bbox, text, conf in results:
                    text_clean = text.strip()
                    if text_clean:
                        easyocr_blocks.append({
                            "text": text_clean,
                            "confidence": float(conf),
                            "bbox": bbox,
                            "engine": "easyocr",
                        })
                if easyocr_blocks:
                    easyocr_conf = float(np.mean([b["confidence"] for b in easyocr_blocks]))
            except Exception:
                pass

        # Try Tesseract
        if HAS_TESSERACT and image_array is not None:
            try:
                data = pytesseract.image_to_data(image_array, output_type=pytesseract.Output.DICT)
                for i in range(len(data['text'])):
                    text = data['text'][i].strip()
                    conf = float(data['conf'][i])
                    if text and conf > 0:
                        tess_blocks.append({
                            "text": text,
                            "confidence": conf / 100.0,
                            "bbox": [data['left'][i], data['top'][i], data['width'][i], data['height'][i]],
                            "engine": "tesseract",
                        })
                if tess_blocks:
                    tess_conf = float(np.mean([b["confidence"] for b in tess_blocks]))
            except Exception:
                pass

        # Return the better result
        if easyocr_conf >= tess_conf:
            return easyocr_blocks, easyocr_conf
        else:
            return tess_blocks, tess_conf


# ═══════════════════════════════════════════════════════════════════════════════
# UNIFIED COMPLIANCE PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def run_full_compliance_scan(
    ocr_result: Dict[str, Any],
    package_shape: str = "rectangular",
    package_dimensions: Optional[Dict[str, float]] = None,
    enable_ai: bool = True,
) -> Dict[str, Any]:
    """
    Run the complete compliance pipeline:
    1. Extract fields from OCR text
    2. Classify product
    3. Run rule engine compliance check
    4. Run toxicity analysis
    5. Estimate font size
    """
    raw_text = ocr_result.get("raw_text", "")
    overall_conf = ocr_result.get("overall_confidence", 0.0)
    text_blocks = ocr_result.get("text_blocks", [])
    image_shape = ocr_result.get("image_shape")

    # Step 1: Extract fields
    extracted_fields = extract_all_fields(raw_text)

    # Step 2: Classify product
    product_class = classify_product(raw_text, extracted_fields)

    # Step 3: Estimate font height
    font_height_mm = estimate_font_height_mm(text_blocks, image_shape) if image_shape else None

    # Step 4: Run rule engine
    is_imported = bool(extracted_fields.get("country_of_origin", {}).get("value"))
    is_food = product_class.get("requires_best_before", False)

    compliance = run_compliance_check(
        extracted_fields=extracted_fields,
        raw_text=raw_text,
        package_shape=package_shape,
        package_dimensions=package_dimensions,
        is_imported=is_imported,
        is_food_item=is_food,
        estimated_font_height_mm=font_height_mm,
    )

    # Step 5: Toxicity analysis
    toxicity = run_toxicity_analysis(raw_text, enable_ai=enable_ai)

    # Step 6: Generate summary
    score = compliance["compliance_score"]
    status = compliance["compliance_status"]
    summary = (
        f"Product classified as '{product_class['label']}'. "
        f"Assessed as {status} with compliance score {score}/100. "
        f"{len(compliance['violations'])} violation(s) and {len(compliance['warnings'])} warning(s) found. "
        f"Toxicity verdict: {toxicity.get('verdict', 'N/A')}."
    )

    return {
        "extracted_fields": extracted_fields,
        "product_classification": product_class,
        "font_size_check": compliance["font_size_check"],
        "compliance_status": status,
        "compliance_score": score,
        "violations": compliance["violations"],
        "warnings": compliance["warnings"],
        "audit_trail": compliance["audit_trail"],
        "pdp_info": compliance.get("pdp_info"),
        "language_check": compliance.get("language_check"),
        "needs_manual_review": [],
        "ai_analysis": {
            "executive_summary": summary,
            "secondary_observations": [],
            "corrective_actions": [v["issue"] for v in compliance["violations"]],
        },
        "toxicity_analysis": toxicity,
        "overall_ocr_confidence": round(overall_conf, 2),
        "stats": {
            "total_checks": compliance["total_checks"],
            "passed": compliance["passed_checks"],
            "failed": compliance["failed_checks"],
            "warnings": compliance["warning_checks"],
            "skipped": compliance["skipped_checks"],
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO MODE (when OCR libraries are not installed)
# ═══════════════════════════════════════════════════════════════════════════════

def create_demo_result(filename: str = "demo_label.jpg") -> Dict[str, Any]:
    """Generate a realistic demo scan result for testing without OCR libraries."""
    demo_raw_text = (
        "INGREDIENTS: Sugar, Skimmed Milk Powder, Cocoa Butter, Cocoa Mass, "
        "Palm Oil, Emulsifiers (322, 476), Artificial Flavour, Salt, "
        "Sodium Benzoate, Tartrazine. "
        "NET QUANTITY: 100 g MRP Rs 150 (inclusive of all taxes) "
        "Mfd by: Demo Foods Pvt Ltd, Industrial Area Phase II, New Delhi 110020 "
        "Batch No: ABC12345XY Mfg Date: 15/JUN/25 "
        "Best Before: 12 months from date of manufacture "
        "Customer care: 1800123456 info@demofoods.in "
        "FSSAI Lic No: 10012345678901 "
        "Made in India "
        "CHOCOLATE FLAVOURED BISCUITS"
    )

    extracted_fields = extract_all_fields(demo_raw_text)
    product_class = classify_product(demo_raw_text, extracted_fields)

    compliance = run_compliance_check(
        extracted_fields=extracted_fields,
        raw_text=demo_raw_text,
        package_shape="rectangular",
        package_dimensions={"height_cm": 15, "width_cm": 8, "depth_cm": 4},
        is_imported=False,
        is_food_item=True,
    )

    toxicity = run_toxicity_analysis(demo_raw_text, enable_ai=False)

    return {
        "extracted_fields": extracted_fields,
        "product_classification": product_class,
        "font_size_check": compliance["font_size_check"],
        "compliance_status": compliance["compliance_status"],
        "compliance_score": compliance["compliance_score"],
        "violations": compliance["violations"],
        "warnings": compliance["warnings"],
        "audit_trail": compliance["audit_trail"],
        "pdp_info": compliance.get("pdp_info"),
        "language_check": compliance.get("language_check"),
        "needs_manual_review": [],
        "ai_analysis": {
            "executive_summary": f"[DEMO MODE] Assessed as {compliance['compliance_status']} with score {compliance['compliance_score']}/100. OCR libraries not installed.",
            "secondary_observations": ["This is a demo result generated without actual OCR processing."],
            "corrective_actions": [v["issue"] for v in compliance["violations"]],
        },
        "toxicity_analysis": toxicity,
        "overall_ocr_confidence": 0.72,
        "stats": {
            "total_checks": compliance["total_checks"],
            "passed": compliance["passed_checks"],
            "failed": compliance["failed_checks"],
            "warnings": compliance["warning_checks"],
            "skipped": compliance["skipped_checks"],
        },
    }
