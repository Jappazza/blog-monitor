"""Blueprint admin — dashboard, run, logs, sources, users.

Autenticazione: session['admin_logged_in'] (separata da Flask-Login).
"""
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import (
    jsonify, redirect, render_template,
    request, session, url_for, flash, current_app
)

from app import db
from app.admin import admin_bp
from app.models import Digest, RunLog, SourceState, User

# ── Stato del processo in corso (modulo-level, ok per single-worker) ──────────
_current_run: dict = {
    "process": None,
    "log_path": None,
    "run_log_id": None,
}


# ── Decorator ─────────────────────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.admin_login"))
        return f(*args, **kwargs)
    return decorated


# ── Login / Logout ─────────────────────────────────────────────────────────────

@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        if u == os.environ.get("ADMIN_USERNAME", "admin") and \
           p == os.environ.get("ADMIN_PASSWORD", "") and \
           os.environ.get("ADMIN_PASSWORD"):
            session["admin_logged_in"] = True
            session.permanent = True
            return redirect(url_for("admin.dashboard"))
        flash("Credenziali non valide.", "danger")
    return render_template("admin/login.html")


@admin_bp.route("/logout")
@admin_required
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("Logout admin effettuato.", "info")
    return redirect(url_for("admin.admin_login"))


# ── Dashboard ──────────────────────────────────────────────────────────────────

@admin_bp.route("/")
@admin_required
def dashboard():
    user_count   = User.query.count()
    digest_count = Digest.query.count()
    last_run     = RunLog.query.order_by(RunLog.started_at.desc()).first()
    last_digest  = Digest.query.order_by(Digest.published_at.desc()).first()
    run_is_active = (
        _current_run["process"] is not None and
        _current_run["process"].poll() is None
    )
    return render_template(
        "admin/dashboard.html",
        user_count=user_count,
        digest_count=digest_count,
        last_run=last_run,
        last_digest=last_digest,
        run_is_active=run_is_active,
    )


# ── Run — trigger manuale ──────────────────────────────────────────────────────

def _script_path() -> Path:
    """Percorso assoluto di blog_monitor_v2.py."""
    env = os.environ.get("BLOG_MONITOR_SCRIPT")
    if env:
        return Path(env)
    # fides/ sta dentro blog-monitor-public/, lo script è nella parent
    return Path(current_app.root_path).parent.parent / "blog_monitor_v2.py"


@admin_bp.route("/run")
@admin_required
def run_page():
    run_is_active = (
        _current_run["process"] is not None and
        _current_run["process"].poll() is None
    )
    recent_runs = RunLog.query.order_by(RunLog.started_at.desc()).limit(5).all()
    script = _script_path()
    return render_template(
        "admin/run.html",
        run_is_active=run_is_active,
        recent_runs=recent_runs,
        script_path=str(script),
        script_exists=script.exists(),
    )


@admin_bp.route("/run/start", methods=["POST"])
@admin_required
def run_start():
    global _current_run

    # Blocca se un run è già in corso
    if _current_run["process"] and _current_run["process"].poll() is None:
        return jsonify({"error": "Run già in corso."}), 409

    script = _script_path()
    if not script.exists():
        return jsonify({"error": f"Script non trovato: {script}"}), 404

    # Crea file di log temporaneo
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_fd, log_path = tempfile.mkstemp(prefix=f"fides_run_{ts}_", suffix=".log")
    os.close(log_fd)

    # Crea RunLog nel DB
    run_log = RunLog(started_at=datetime.now(timezone.utc), status=RunLog.STATUS_RUNNING)
    db.session.add(run_log)
    db.session.commit()

    # Avvia lo script in background, stdout+stderr → log file
    with open(log_path, "w") as lf:
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(script.parent),
            stdout=lf,
            stderr=subprocess.STDOUT,
        )

    _current_run["process"]   = proc
    _current_run["log_path"]  = log_path
    _current_run["run_log_id"] = run_log.id

    return jsonify({"run_log_id": run_log.id, "log_path": log_path})


@admin_bp.route("/run/status")
@admin_required
def run_status():
    global _current_run

    proc     = _current_run.get("process")
    log_path = _current_run.get("log_path")

    if proc is None:
        return jsonify({"running": False, "lines": [], "exit_code": None})

    exit_code = proc.poll()
    running   = exit_code is None

    lines = []
    if log_path and Path(log_path).exists():
        with open(log_path, errors="replace") as f:
            lines = f.read().splitlines()[-200:]  # ultime 200 righe

    # Se terminato, aggiorna RunLog
    if not running and _current_run.get("run_log_id"):
        rl = RunLog.query.get(_current_run["run_log_id"])
        if rl and rl.status == RunLog.STATUS_RUNNING:
            rl.completed_at = datetime.now(timezone.utc)
            rl.status = RunLog.STATUS_SUCCESS if exit_code == 0 else RunLog.STATUS_ERROR
            db.session.commit()
        _current_run["process"] = None  # libera slot

    return jsonify({"running": running, "lines": lines, "exit_code": exit_code})


# ── Logs ───────────────────────────────────────────────────────────────────────

@admin_bp.route("/logs")
@admin_required
def logs():
    runs = RunLog.query.order_by(RunLog.started_at.desc()).limit(20).all()
    return render_template("admin/logs.html", runs=runs)


@admin_bp.route("/logs/<int:run_id>")
@admin_required
def log_detail(run_id: int):
    run = RunLog.query.get_or_404(run_id)
    return render_template("admin/log_detail.html", run=run)


# ── Sources ────────────────────────────────────────────────────────────────────

@admin_bp.route("/sources")
@admin_required
def sources():
    import json
    from pathlib import Path as P

    # Legge config.json (stesso approccio di user/routes.py)
    candidates = [
        P(current_app.root_path).parent / "config" / "config.json",
        P(current_app.root_path).parent.parent / "config" / "config.json",
    ]
    config_path = next((c for c in candidates if c.exists()), None)
    config_sources = []
    if config_path:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        config_sources = data.get("blogs", [])

    # Merge con SourceState dal DB
    states = {s.source_name: s for s in SourceState.query.all()}
    sources_list = []
    for b in config_sources:
        name = b.get("name", "")
        state = states.get(name)
        sources_list.append({
            "name": name,
            "url": b.get("url", "#"),
            "enabled_config": b.get("enabled", True),
            "db_state": state,
        })

    return render_template("admin/sources.html", sources=sources_list)


@admin_bp.route("/sources/<path:source_name>/toggle", methods=["POST"])
@admin_required
def source_toggle(source_name: str):
    state = SourceState.query.filter_by(source_name=source_name).first()
    if not state:
        state = SourceState(source_name=source_name, enabled=True)
        db.session.add(state)
    state.enabled = not state.enabled
    db.session.commit()
    return redirect(url_for("admin.sources"))


# ── Users ──────────────────────────────────────────────────────────────────────

@admin_bp.route("/users")
@admin_required
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=all_users)
