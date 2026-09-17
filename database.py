"""
database.py
============
SQLite persistence layer for the Pack Proof Legal Metrology Compliance Engine.

Includes user authentication, audit log storage with extended schema,
stats aggregation, search/pagination, and product repository.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


def _hash_password(password: str) -> str:
    """Generate password hash using pbkdf2 for Python 3.9+ compatibility."""
    return generate_password_hash(password, method="pbkdf2:sha256")


DB_PATH = Path(__file__).resolve().parent / "data" / "audit.db"


def _get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _column_names(conn, table: str):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

def init_db():
    """Create all tables (idempotent, migration-safe)."""
    conn = _get_conn()

    # Users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'viewer',
            full_name TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # Audit logs table (extended schema)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            scan_id TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            status TEXT NOT NULL,
            confidence REAL NOT NULL,
            violations TEXT NOT NULL,
            warnings TEXT NOT NULL,
            audit_trail TEXT NOT NULL,
            fields TEXT,
            font_size_check TEXT,
            compliance_score INTEGER,
            needs_manual_review TEXT,
            ai_analysis TEXT,
            toxicity_analysis TEXT,
            product_category TEXT,
            package_shape TEXT,
            package_dimensions TEXT,
            pdp_area_cm2 REAL,
            raw_ocr_text TEXT,
            rule_violations TEXT,
            product_classification TEXT,
            language_check TEXT,
            scanned_by TEXT
        )
    """)

    # Migration path for pre-existing databases
    existing = _column_names(conn, "audit_logs")
    migrations = {
        "fields": "ALTER TABLE audit_logs ADD COLUMN fields TEXT",
        "font_size_check": "ALTER TABLE audit_logs ADD COLUMN font_size_check TEXT",
        "compliance_score": "ALTER TABLE audit_logs ADD COLUMN compliance_score INTEGER",
        "needs_manual_review": "ALTER TABLE audit_logs ADD COLUMN needs_manual_review TEXT",
        "ai_analysis": "ALTER TABLE audit_logs ADD COLUMN ai_analysis TEXT",
        "toxicity_analysis": "ALTER TABLE audit_logs ADD COLUMN toxicity_analysis TEXT",
        "product_category": "ALTER TABLE audit_logs ADD COLUMN product_category TEXT",
        "package_shape": "ALTER TABLE audit_logs ADD COLUMN package_shape TEXT",
        "package_dimensions": "ALTER TABLE audit_logs ADD COLUMN package_dimensions TEXT",
        "pdp_area_cm2": "ALTER TABLE audit_logs ADD COLUMN pdp_area_cm2 REAL",
        "raw_ocr_text": "ALTER TABLE audit_logs ADD COLUMN raw_ocr_text TEXT",
        "rule_violations": "ALTER TABLE audit_logs ADD COLUMN rule_violations TEXT",
        "product_classification": "ALTER TABLE audit_logs ADD COLUMN product_classification TEXT",
        "language_check": "ALTER TABLE audit_logs ADD COLUMN language_check TEXT",
        "scanned_by": "ALTER TABLE audit_logs ADD COLUMN scanned_by TEXT",
    }
    for col, ddl in migrations.items():
        if col not in existing:
            try:
                conn.execute(ddl)
            except sqlite3.OperationalError:
                pass  # Column already exists

    conn.commit()

    # Seed default users if none exist
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        _seed_default_users(conn)

    conn.close()


def _seed_default_users(conn):
    """Create default users on first run."""
    users = [
        ("admin", "admin123", "admin", "System Administrator"),
        ("inspector", "inspect123", "inspector", "Field Inspector"),
        ("viewer", "view123", "viewer", "Public Viewer"),
    ]
    now = datetime.now().isoformat()
    for username, password, role, full_name in users:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, full_name, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, _hash_password(password), role, full_name, now),
        )
    conn.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# USER AUTHENTICATION
# ═══════════════════════════════════════════════════════════════════════════════

def authenticate_user(username: str, password: str):
    """Verify credentials. Returns user dict or None."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if row and check_password_hash(row["password_hash"], password):
        return {
            "id": row["id"],
            "username": row["username"],
            "role": row["role"],
            "full_name": row["full_name"],
        }
    return None


def get_user_by_id(user_id: int):
    """Fetch user by ID."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return {
            "id": row["id"],
            "username": row["username"],
            "role": row["role"],
            "full_name": row["full_name"],
        }
    return None


def create_user(username: str, password: str, role: str = "viewer", full_name: str = ""):
    """Create a new user."""
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, full_name, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, _hash_password(password), role, full_name, datetime.now().isoformat()),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_all_users():
    """Get all users (for admin panel)."""
    conn = _get_conn()
    rows = conn.execute("SELECT id, username, role, full_name, created_at FROM users ORDER BY id").fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIT LOG OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def save_audit_log(
    scan_id,
    filename,
    compliance_status,
    confidence,
    violations,
    warnings,
    audit_trail,
    fields=None,
    font_size_check=None,
    compliance_score=None,
    needs_manual_review=None,
    ai_analysis=None,
    toxicity_analysis=None,
    product_category=None,
    package_shape=None,
    package_dimensions=None,
    pdp_area_cm2=None,
    raw_ocr_text=None,
    rule_violations=None,
    product_classification=None,
    language_check=None,
    scanned_by=None,
):
    """Save one verification run to SQLite."""
    conn = _get_conn()
    timestamp = datetime.now().isoformat()

    # Serialize violations/warnings to JSON
    # Handle both list-of-dicts and list-of-strings
    def _serialize_list(items):
        if items and isinstance(items[0], dict):
            return json.dumps(items)
        return json.dumps(items or [])

    conn.execute(
        """
        INSERT INTO audit_logs (
            timestamp, scan_id, filename, status, confidence,
            violations, warnings, audit_trail,
            fields, font_size_check, compliance_score,
            needs_manual_review, ai_analysis, toxicity_analysis,
            product_category, package_shape, package_dimensions,
            pdp_area_cm2, raw_ocr_text, rule_violations,
            product_classification, language_check, scanned_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp, scan_id, filename, compliance_status, confidence,
            _serialize_list(violations), _serialize_list(warnings), json.dumps(audit_trail),
            json.dumps(fields or {}),
            json.dumps(font_size_check) if font_size_check else None,
            compliance_score,
            json.dumps(needs_manual_review or []),
            json.dumps(ai_analysis) if ai_analysis else None,
            json.dumps(toxicity_analysis) if toxicity_analysis else None,
            product_category,
            package_shape,
            json.dumps(package_dimensions) if package_dimensions else None,
            pdp_area_cm2,
            raw_ocr_text,
            json.dumps(rule_violations) if rule_violations else None,
            json.dumps(product_classification) if product_classification else None,
            json.dumps(language_check) if language_check else None,
            scanned_by,
        ),
    )

    conn.commit()
    conn.close()


def _parse_log_row(row):
    """Convert a sqlite3.Row into a dict with JSON fields parsed."""
    def _safe_json(val):
        if val is None:
            return None
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val

    return {
        "id": row["id"],
        "timestamp": row["timestamp"],
        "scan_id": row["scan_id"],
        "filename": row["filename"],
        "status": row["status"],
        "confidence": row["confidence"],
        "violations": _safe_json(row["violations"]) or [],
        "warnings": _safe_json(row["warnings"]) or [],
        "audit_trail": _safe_json(row["audit_trail"]) or [],
        "fields": _safe_json(row["fields"]) or {},
        "font_size_check": _safe_json(row["font_size_check"]),
        "compliance_score": row["compliance_score"],
        "needs_manual_review": _safe_json(row["needs_manual_review"]) or [],
        "ai_analysis": _safe_json(row["ai_analysis"]),
        "toxicity_analysis": _safe_json(row["toxicity_analysis"]),
        "product_category": row["product_category"] if "product_category" in row.keys() else None,
        "package_shape": row["package_shape"] if "package_shape" in row.keys() else None,
        "package_dimensions": _safe_json(row["package_dimensions"]) if "package_dimensions" in row.keys() else None,
        "pdp_area_cm2": row["pdp_area_cm2"] if "pdp_area_cm2" in row.keys() else None,
        "raw_ocr_text": row["raw_ocr_text"] if "raw_ocr_text" in row.keys() else None,
        "rule_violations": _safe_json(row["rule_violations"]) if "rule_violations" in row.keys() else None,
        "product_classification": _safe_json(row["product_classification"]) if "product_classification" in row.keys() else None,
        "language_check": _safe_json(row["language_check"]) if "language_check" in row.keys() else None,
        "scanned_by": row["scanned_by"] if "scanned_by" in row.keys() else None,
    }


def fetch_all_logs():
    """Get all saved audit logs, newest first."""
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM audit_logs ORDER BY id DESC").fetchall()
    conn.close()
    return [_parse_log_row(row) for row in rows]


def fetch_log_by_scan_id(scan_id: str):
    """Get one record by scan_id."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM audit_logs WHERE scan_id = ?", (scan_id,)).fetchone()
    conn.close()
    return _parse_log_row(row) if row else None


def search_logs(query: str = "", status_filter: str = "", page: int = 1, per_page: int = 20):
    """Search and paginate audit logs."""
    conn = _get_conn()

    conditions = []
    params = []

    if query:
        conditions.append("(filename LIKE ? OR scan_id LIKE ? OR product_category LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])

    if status_filter and status_filter != "all":
        conditions.append("status = ?")
        params.append(status_filter)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Count
    count = conn.execute(f"SELECT COUNT(*) FROM audit_logs WHERE {where_clause}", params).fetchone()[0]

    # Paginated results
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM audit_logs WHERE {where_clause} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    conn.close()

    return {
        "logs": [_parse_log_row(row) for row in rows],
        "total": count,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (count + per_page - 1) // per_page),
    }


def fetch_stats():
    """Aggregate dashboard statistics."""
    conn = _get_conn()

    total = conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    compliant = conn.execute("SELECT COUNT(*) FROM audit_logs WHERE status = 'COMPLIANT'").fetchone()[0]
    warnings_count = conn.execute("SELECT COUNT(*) FROM audit_logs WHERE status = 'COMPLIANT WITH WARNINGS'").fetchone()[0]
    non_compliant = conn.execute("SELECT COUNT(*) FROM audit_logs WHERE status = 'NON-COMPLIANT'").fetchone()[0]
    rescan = conn.execute("SELECT COUNT(*) FROM audit_logs WHERE status = 'RESCAN NEEDED'").fetchone()[0]

    avg_score_row = conn.execute("SELECT AVG(compliance_score) FROM audit_logs WHERE compliance_score IS NOT NULL").fetchone()
    avg_score = round(avg_score_row[0], 1) if avg_score_row[0] is not None else 0

    avg_conf_row = conn.execute("SELECT AVG(confidence) FROM audit_logs").fetchone()
    avg_confidence = round(avg_conf_row[0] * 100, 1) if avg_conf_row[0] is not None and avg_conf_row[0] > 0 else 0

    # Recent 10
    recent_rows = conn.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 10").fetchall()
    recent = [_parse_log_row(row) for row in recent_rows]

    # Toxicity stats
    tox_rows = conn.execute("SELECT toxicity_analysis FROM audit_logs WHERE toxicity_analysis IS NOT NULL").fetchall()
    tox_safe, tox_caution, tox_not_rec = 0, 0, 0
    avg_tox_score_sum, avg_tox_count = 0, 0
    for trow in tox_rows:
        try:
            tox = json.loads(trow["toxicity_analysis"])
        except (json.JSONDecodeError, TypeError):
            continue
        v = tox.get("verdict", "")
        if v == "SAFE":
            tox_safe += 1
        elif v == "USE WITH CAUTION":
            tox_caution += 1
        elif v == "NOT RECOMMENDED":
            tox_not_rec += 1
        ts = tox.get("toxicity_score")
        if ts is not None:
            avg_tox_score_sum += ts
            avg_tox_count += 1

    avg_tox_score = round(avg_tox_score_sum / avg_tox_count, 1) if avg_tox_count else 0

    # Product category breakdown
    cat_rows = conn.execute(
        "SELECT product_category, COUNT(*) as cnt FROM audit_logs WHERE product_category IS NOT NULL GROUP BY product_category"
    ).fetchall()
    categories = {row["product_category"]: row["cnt"] for row in cat_rows}

    conn.close()

    return {
        "total_scans": total,
        "compliant": compliant,
        "warnings": warnings_count,
        "non_compliant": non_compliant,
        "rescan": rescan,
        "avg_score": avg_score,
        "avg_confidence": avg_confidence,
        "compliance_rate": round(compliant / total * 100, 1) if total else 0,
        "recent_scans": recent,
        "toxicity": {
            "safe": tox_safe,
            "caution": tox_caution,
            "not_recommended": tox_not_rec,
            "avg_score": avg_tox_score,
        },
        "categories": categories,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LEGACY HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def create_report(audit):
    """Plain-text report for CLI/debug view."""
    score = audit.get("compliance_score")
    score_str = f"{score}/100" if score is not None else "N/A"

    tox = audit.get("toxicity_analysis") or {}
    tox_line = (
        f'{tox.get("verdict", "N/A")} (Toxicity Score: {tox.get("toxicity_score", "N/A")}/100)'
        if tox
        else "N/A"
    )

    report = f"""
PACK PROOF VERIFICATION REPORT
================================

Status: {audit["status"]}
Score: {score_str}

Overall Confidence: {audit["confidence"] * 100:.0f}%

Ingredient Toxicity Advisory: {tox_line}

Violations:
"""
    for violation in audit.get("violations", []):
        if isinstance(violation, dict):
            report += f"- [{violation.get('rule', '')}] {violation.get('issue', '')}\n"
        else:
            report += f"- {violation}\n"

    report += "\nWarnings:\n"
    for warning in audit.get("warnings", []):
        if isinstance(warning, dict):
            report += f"- [{warning.get('rule', '')}] {warning.get('issue', '')}\n"
        else:
            report += f"- {warning}\n"

    return report


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
    print(f"DB path: {DB_PATH}")
