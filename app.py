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
  /rules           → Legal Metrology rules explorer
  /api/stats       → JSON endpoint for dashboard charts
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
from rule_engine import get_all_rules_summary

# ═══════════════════════════════════════════════════════════════════════════════
# APP CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "pack-proof-dev-secret-key-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB max upload

UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Initialize database on startup
init_db()


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

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

        # Parse package dimensions
        package_dimensions = None
        try:
            height = float(request.form.get("pkg_height", 0) or 0)
            width = float(request.form.get("pkg_width", 0) or 0)
            depth = float(request.form.get("pkg_depth", 0) or 0)
            if height > 0 and width > 0:
                package_dimensions = {
                    "height_cm": height,
                    "width_cm": width,
                    "depth_cm": depth,
                }
        except (ValueError, TypeError):
            pass

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
            from ocr_engine import HybridOCREngine, run_full_compliance_scan, is_ocr_available

            if is_ocr_available():
                engine = HybridOCREngine()
                if len(image_paths) == 1:
                    ocr_result = engine.extract(image_paths[0])
                else:
                    ocr_result = engine.extract_multiple(image_paths)

                result = run_full_compliance_scan(
                    ocr_result,
                    package_shape=package_shape,
                    package_dimensions=package_dimensions,
                    enable_ai=use_ai,
                )
            else:
                # Demo mode
                from ocr_engine import create_demo_result
                result = create_demo_result(image_paths[0])

        except Exception as e:
            import traceback; traceback.print_exc()
            flash(f"OCR processing failed: {str(e)}", "error")
            return redirect(url_for("scan"))

        # Save to database
        scan_id = str(uuid.uuid4())
        filename_record = ", ".join([os.path.basename(p) for p in image_paths])

        # Extract product classification info
        product_class = result.get("product_classification", {})
        pdp_info = result.get("pdp_info", {})

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
            product_category=product_class.get("label"),
            package_shape=package_shape,
            package_dimensions=package_dimensions,
            pdp_area_cm2=pdp_info.get("pdp_area_cm2") if pdp_info else None,
            raw_ocr_text=None,  # Don't store full text to save space
            product_classification=product_class,
            language_check=result.get("language_check"),
            scanned_by=request.current_user.username,
        )

        return redirect(url_for("scan_result", scan_id=scan_id))

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


@app.route("/rules")
@login_required
def rules_explorer():
    rules = get_all_rules_summary()
    return render_template("rules_explorer.html", rules=rules, active_page="rules")


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


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(e):
    if session.get("user_id"):
        return render_template("base.html", active_page="", error_code=404, error_message="Page not found."), 404
    return redirect(url_for("login"))


@app.errorhandler(403)
def forbidden(e):
    return render_template("base.html", active_page="", error_code=403, error_message="Access denied. Insufficient permissions."), 403


# ═══════════════════════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════════════════════

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
