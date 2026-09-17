"""
app.py
=======
Flask web application for Pack Proof — Legal Metrology Compliance Engine.

Routes:
  /                → Redirect to dashboard or login
  /login           → Authentication page
  /logout          → End session
  /dashboard       → KPI dashboard with charts
  /scan            → Image upload & compliance scan
  /scan/<scan_id>  → Detailed scan result view
  /history         → Paginated scan history with search/filter
  /api/report/<id>/pdf → Download PDF report
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_file, abort, jsonify
)

from database import (
    init_db, authenticate_user, get_user_by_id,
    save_audit_log, fetch_log_by_scan_id, search_logs, fetch_stats
)
from report_renderer import render_pdf_report

# ── App Configuration ────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "pack-proof-dev-secret-key-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB max upload

UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Initialize database on startup
init_db()


# ── Auth Helpers ─────────────────────────────────────────────────────────────

class UserProxy:
    """Minimal user object for template rendering."""
    def __init__(self, user_dict):
        self.id = user_dict["id"]
        self.username = user_dict["username"]
        self.role = user_dict["role"]
        self.full_name = user_dict.get("full_name", "")
        self.is_authenticated = True

    def __getattr__(self, name):
        return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return redirect(url_for("login"))
        user = get_user_by_id(user_id)
        if not user:
            session.clear()
            return redirect(url_for("login"))
        request.current_user = UserProxy(user)
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if request.current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


@app.context_processor
def inject_user():
    """Make current_user available in all templates."""
    user_id = session.get("user_id")
    if user_id:
        user = get_user_by_id(user_id)
        if user:
            return {"current_user": UserProxy(user)}
    return {"current_user": None}


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = authenticate_user(username, password)
        if user:
            session["user_id"] = user["id"]
            session.permanent = True
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid username or password. Please try again."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    stats = fetch_stats()
    return render_template("dashboard.html", stats=stats, active_page="dashboard")


@app.route("/scan", methods=["GET", "POST"])
@login_required
def scan():
    if request.current_user.role == "viewer":
        flash("Viewers cannot perform scans.", "warning")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        files = request.files.getlist("images")
        if not files or all(f.filename == "" for f in files):
            flash("Please upload at least one image.", "error")
            return redirect(url_for("scan"))

        package_shape = request.form.get("package_shape", "rectangular")
        use_ai = "use_ai" in request.form

        # Save uploaded files
        image_paths = []
        for f in files:
            if f.filename:
                safe_name = f"{uuid.uuid4().hex[:8]}_{f.filename}"
                save_path = UPLOAD_DIR / safe_name
                f.save(str(save_path))
                image_paths.append(str(save_path))

        if not image_paths:
            flash("No valid images uploaded.", "error")
            return redirect(url_for("scan"))

        # Run OCR + Compliance
        try:
            from unified_compliance_engine import HybridOCREngine, run_full_check_from_ocr_result

            engine = HybridOCREngine()
            if len(image_paths) == 1:
                ocr_result = engine.extract(image_paths[0])
            else:
                ocr_result = engine.extract_multiple(image_paths)

            result = run_full_check_from_ocr_result(
                ocr_result,
                package_shape=package_shape,
                enable_ai_rescue=use_ai,
                enable_ai_synthesis=use_ai,
            )

            # Save to database
            scan_id = str(uuid.uuid4())
            filename_record = ", ".join([os.path.basename(p) for p in image_paths])

            save_audit_log(
                scan_id=scan_id,
                filename=filename_record,
                compliance_status=result["compliance_status"],
                confidence=result.get("overall_ocr_confidence", 0.0),
                violations=result["violations"],
                warnings=result["warnings"],
                audit_trail=result["audit_trail"],
                fields=result["extracted_fields"],
                font_size_check=result["font_size_check"],
                compliance_score=result.get("compliance_score"),
                needs_manual_review=result.get("needs_manual_review"),
                ai_analysis=result.get("ai_analysis"),
                toxicity_analysis=result.get("toxicity_analysis"),
            )

            return redirect(url_for("scan_result", scan_id=scan_id))

        except Exception as e:
            flash(f"Scan failed: {str(e)}", "error")
            return redirect(url_for("scan"))

    return render_template("scan.html", active_page="scan")


@app.route("/scan/<scan_id>")
@login_required
def scan_result(scan_id):
    record = fetch_log_by_scan_id(scan_id)
    if not record:
        abort(404)
    return render_template("scan_result.html", record=record, active_page="scan")


@app.route("/history")
@login_required
def history():
    query = request.args.get("q", "")
    status_filter = request.args.get("status", "")
    page = request.args.get("page", 1, type=int)

    data = search_logs(query=query, status_filter=status_filter, page=page)
    return render_template(
        "history.html",
        data=data,
        query=query,
        status_filter=status_filter,
        active_page="history",
    )


@app.route("/api/report/<scan_id>/pdf")
@login_required
def download_pdf(scan_id):
    record = fetch_log_by_scan_id(scan_id)
    if not record:
        abort(404)

    output_filename = f"report_{scan_id[:8]}.pdf"
    report_path = render_pdf_report(record, output_filename)

    if not os.path.exists(report_path):
        abort(500)

    # Determine if it's PDF or HTML fallback
    is_pdf = report_path.endswith(".pdf")
    mimetype = "application/pdf" if is_pdf else "text/html"
    download_name = output_filename if is_pdf else output_filename.replace(".pdf", ".html")

    return send_file(
        report_path,
        mimetype=mimetype,
        as_attachment=True,
        download_name=download_name,
    )


@app.route("/api/stats")
@login_required
def api_stats():
    stats = fetch_stats()
    return jsonify(stats)


# ── Demo Data Generator ─────────────────────────────────────────────────────

def _create_demo_result(filename):
    """Generate a realistic demo scan result when OCR libraries aren't installed."""
    from toxicity_engine import run_toxicity_analysis

    demo_raw_text = (
        "INGREDIENTS: Sugar, Skimmed Milk Powder, Cocoa Butter, Cocoa Mass, "
        "Palm Oil, Emulsifiers (322, 476), Artificial Flavour, Salt, "
        "Sodium Benzoate, Tartrazine. "
        "NET QUANTITY: 100 g MRP Rs 150 "
        "Mfd by: Demo Foods Pvt Ltd, Industrial Area, New Delhi "
        "Batch: ABC12345XY Mfg Date: 15/JUN/25 "
        "Customer care: 1800123456"
    )

    toxicity = run_toxicity_analysis(demo_raw_text, enable_ai=False)

    fields = {
        "net_quantity": {"value": "NET QUANTITY: 100 g", "confidence": 1.0, "source": "regex"},
        "mrp": {"value": "MRP ₹ 150", "confidence": 0.95, "source": "regex"},
        "batch_details": {"value": "Batch: ABC12345XY", "confidence": 0.85, "source": "regex"},
        "manufacturer": {"value": "Mfd by: Demo Foods Pvt Ltd, Industrial Area, New Delhi", "confidence": 0.80, "source": "regex"},
        "mfg_date": {"value": "Mfg Date: 15/JUN/25", "confidence": 0.95, "source": "regex"},
        "consumer_care": {"value": "Customer care: 1800123456", "confidence": 0.85, "source": "regex"},
        "common_name": {"value": None, "confidence": 0.0, "source": "regex"},
    }

    audit_trail = []
    violations = []
    warnings = []
    step = 1
    for field_key, field_data in fields.items():
        if field_data["value"]:
            result_status = "pass"
            reason = "Requirement satisfied."
        else:
            if field_key in ["manufacturer", "net_quantity", "mrp"]:
                result_status = "fail"
                reason = f"{field_key.replace('_', ' ').title()} not clearly detected."
                violations.append(f"{field_key.replace('_', ' ').title()}: {reason}")
            else:
                result_status = "warning"
                reason = f"Could not confidently identify {field_key.replace('_', ' ')}."
                warnings.append(f"{field_key.replace('_', ' ').title()}: {reason}")

        audit_trail.append({
            "step": step,
            "field": field_key,
            "label": field_key.replace("_", " ").title(),
            "result": result_status,
            "confidence": field_data["confidence"],
            "reason": reason,
            "source": field_data["source"],
        })
        step += 1

    score = 100 - (len(violations) * 20 + len(warnings) * 10)
    status = "COMPLIANT" if not violations and not warnings else ("NON-COMPLIANT" if violations else "COMPLIANT WITH WARNINGS")

    return {
        "status": status,
        "compliance_score": max(0, score),
        "confidence": 0.72,
        "violations": violations,
        "warnings": warnings,
        "audit_trail": audit_trail,
        "fields": fields,
        "font_size_check": {
            "value": "4.5 mm", "confidence": 1.0, "issue": None,
            "panel_area_cm2": 80.0, "minimum_required_mm": 1.5, "compliant": True,
        },
        "needs_manual_review": [],
        "ai_analysis": {
            "executive_summary": f"Assessed as {status} with score {max(0, score)}/100. Demo mode — OCR libraries not installed.",
            "secondary_observations": ["This is a demo result generated without actual OCR processing."],
            "corrective_actions": violations,
        },
        "toxicity_analysis": toxicity,
    }


# ── Error Handlers ───────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    if session.get("user_id"):
        return """<div style="text-align:center;padding:60px;font-family:Inter,sans-serif;">
            <h1 style="font-size:48px;color:#EF4444;">404</h1>
            <p style="color:#64748B;">Page not found.</p>
            <a href="/" style="color:#2E7DFF;">Go to Dashboard</a></div>""", 404
    return redirect(url_for("login"))


@app.errorhandler(403)
def forbidden(e):
    return """<div style="text-align:center;padding:60px;font-family:Inter,sans-serif;">
        <h1 style="font-size:48px;color:#F59E0B;">403</h1>
        <p style="color:#64748B;">Access denied. Insufficient permissions.</p>
        <a href="/" style="color:#2E7DFF;">Go to Dashboard</a></div>""", 403


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Pack Proof — Legal Metrology Compliance Engine")
    print("  Starting on http://127.0.0.1:5001")
    print("=" * 60)
    print("\n  Default credentials:")
    print("    Admin:     admin / admin123")
    print("    Inspector: inspector / inspect123")
    print("    Viewer:    viewer / view123")
    print("=" * 60 + "\n")

    app.run(debug=True, host="0.0.0.0", port=5001)
