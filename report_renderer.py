"""
report_renderer.py
===================
PDF/HTML report generation for Pack Proof compliance reports.

Uses Jinja2 for templating + WeasyPrint for PDF generation.
Falls back to HTML-only if WeasyPrint is not available.
"""

import os
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"


# Legal rule references for each field
LEGAL_REFS = {
    "manufacturer": "Rule 6(1)(a)",
    "net_quantity": "Rule 6(1)(b)",
    "common_name": "Rule 6(1)(c)",
    "mfg_date": "Rule 6(1)(d)",
    "mrp": "Rule 6(1)(e)",
    "best_before": "Rule 6(1)(f)",
    "consumer_care": "Rule 6(1)(g)",
    "country_of_origin": "Rule 6(1)(h)",
    "batch_details": "Rule 6(1)(h)",
    "fssai_license": "FSS Act 2006",
    "font_size": "Rule 7",
    "language": "Rule 6(3)",
}


def _get_disclosure_rows(record):
    """Build disclosure rows for the report template."""
    rows = []
    for step in record.get("audit_trail", []):
        field_data = record.get("fields", {}).get(step["field"], {})
        rows.append({
            "label": step.get("label", step["field"]),
            "legal_reference": step.get("rule", LEGAL_REFS.get(step["field"], "—")),
            "value": field_data.get("value") if field_data else None,
            "source": step.get("source", "—"),
            "result": step["result"],
            "severity": step.get("severity", "—"),
            "confidence": step.get("confidence", 0),
        })
    return rows


def render_pdf_report(record, output_filename=None):
    """
    Render a compliance report to PDF (or HTML fallback).

    Returns the path to the generated file.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if output_filename is None:
        output_filename = f"report_{record['scan_id'][:8]}.pdf"

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("report_template.html")

    # Prepare context
    confidence_pct = round(record.get("confidence", 0) * 100, 1)

    # Handle violations/warnings that may be dicts or strings
    violations_display = []
    for v in record.get("violations", []):
        if isinstance(v, dict):
            violations_display.append(f"[{v.get('rule', '')}] {v.get('issue', v.get('label', ''))}")
        else:
            violations_display.append(str(v))

    warnings_display = []
    for w in record.get("warnings", []):
        if isinstance(w, dict):
            warnings_display.append(f"[{w.get('rule', '')}] {w.get('issue', w.get('label', ''))}")
        else:
            warnings_display.append(str(w))

    context = {
        "scan_id": record["scan_id"],
        "timestamp": record.get("timestamp", datetime.now().isoformat()),
        "filename": record.get("filename", "Unknown"),
        "confidence": confidence_pct,
        "compliance_status": record.get("status", "UNKNOWN"),
        "compliance_score": record.get("compliance_score"),
        "disclosure_rows": _get_disclosure_rows(record),
        "needs_manual_review": record.get("needs_manual_review", []),
        "font_size_check": record.get("font_size_check"),
        "violations": violations_display,
        "warnings": warnings_display,
        "ai_analysis": record.get("ai_analysis"),
        "toxicity_analysis": record.get("toxicity_analysis"),
        "audit_trail": record.get("audit_trail", []),
        "product_classification": record.get("product_classification"),
        "language_check": record.get("language_check"),
        "logo_path": None,
        "generated_at": datetime.now().strftime("%d %B %Y, %I:%M %p"),
    }

    html_content = template.render(**context)
    output_path = REPORTS_DIR / output_filename

    # Try WeasyPrint for PDF
    try:
        from weasyprint import HTML
        HTML(string=html_content).write_pdf(str(output_path))
        return str(output_path)
    except ImportError:
        # Fallback: save as HTML
        html_output = output_path.with_suffix(".html")
        html_output.write_text(html_content, encoding="utf-8")
        return str(html_output)
    except Exception:
        # Fallback: save as HTML
        html_output = output_path.with_suffix(".html")
        html_output.write_text(html_content, encoding="utf-8")
        return str(html_output)
