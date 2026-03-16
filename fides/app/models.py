"""Modelli SQLAlchemy per Fides.

Tabelle:
  - User          → utenti registrati (Flask-Login)
  - Digest        → digest settimanali generati dallo script
  - Article       → articoli singoli dentro un digest
  - RunLog        → log di ogni esecuzione dello script
  - SourceState   → stato e configurazione delle fonti monitorate

Note sui tipi array/JSON:
  Usiamo db.JSON per i campi array su tutti i dialetti. In produzione
  (PostgreSQL) si potrebbe usare ARRAY nativo, ma JSON è sufficiente
  per l'MVP e funziona sia su SQLite (dev) che su PostgreSQL (produzione).
"""
import uuid
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


# ── helper ────────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── User ─────────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    """Utente registrato. Autenticazione via Flask-Login."""

    __tablename__ = "users"

    # UUID come primary key — più sicuro di un intero incrementale
    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    last_login = db.Column(db.DateTime(timezone=True), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def set_password(self, password: str) -> None:
        """Hasha e salva la password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifica la password in chiaro contro l'hash salvato."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.email}>"


# ── Digest ────────────────────────────────────────────────────────────────────

class Digest(db.Model):
    """Digest settimanale generato da blog_monitor_v2.py."""

    __tablename__ = "digests"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False)          # es. "Digest #12 — 5 marzo 2026"
    published_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    article_count = db.Column(db.Integer, default=0)
    summary = db.Column(db.Text, nullable=True)                # anteprima 3 temi principali
    # Lista di nomi fonte per i badge nella lista (JSON: ["Goldman Sachs", "ECB", ...])
    sources_tags = db.Column(db.JSON, nullable=True, default=list)
    raw_markdown = db.Column(db.Text, nullable=True)           # output originale script

    # Relazione uno-a-molti con Article
    articles = db.relationship(
        "Article", backref="digest", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Digest #{self.id} — {self.published_at.date() if self.published_at else 'n/a'}>"


# ── Article ───────────────────────────────────────────────────────────────────

class Article(db.Model):
    """Articolo singolo dentro un Digest."""

    __tablename__ = "articles"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    digest_id = db.Column(
        db.Integer, db.ForeignKey("digests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = db.Column(db.String(500), nullable=False)
    source = db.Column(db.String(100), nullable=True)          # es. "Goldman Sachs"
    relevance_score = db.Column(db.Integer, nullable=True)     # 1-10
    why_relevant = db.Column(db.Text, nullable=True)           # "Perché è rilevante"
    # JSON list di bullet point (["punto 1", "punto 2", ...])
    key_points = db.Column(db.JSON, nullable=True, default=list)
    # JSON list di 3 spunti di conversazione
    conversation_starters = db.Column(db.JSON, nullable=True, default=list)
    original_url = db.Column(db.String(500), nullable=True)
    published_date = db.Column(db.Date, nullable=True)

    def __repr__(self) -> str:
        return f"<Article {self.id} — {self.title[:40]}>"


# ── RunLog ────────────────────────────────────────────────────────────────────

class RunLog(db.Model):
    """Log di ogni esecuzione di blog_monitor_v2.py."""

    __tablename__ = "run_logs"

    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_PARTIAL = "partial"
    STATUS_ERROR   = "error"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    started_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_RUNNING)
    articles_found = db.Column(db.Integer, default=0)
    digest_id = db.Column(
        db.Integer, db.ForeignKey("digests.id", ondelete="SET NULL"), nullable=True
    )
    # JSON: {"Goldman Sachs": "timeout", "ECB": "parse_error"}
    error_details = db.Column(db.JSON, nullable=True)
    log_output = db.Column(db.Text, nullable=True)             # output completo per debug

    @property
    def duration_seconds(self):
        """Durata in secondi, None se ancora in corso."""
        if self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            return int(delta.total_seconds())
        return None

    def __repr__(self) -> str:
        return f"<RunLog #{self.id} — {self.status}>"


# ── SourceState ───────────────────────────────────────────────────────────────

class SourceState(db.Model):
    """Stato persistente di ogni fonte configurata in config.json."""

    __tablename__ = "source_states"

    STATUS_OK      = "ok"
    STATUS_ERROR   = "error"
    STATUS_TIMEOUT = "timeout"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    source_name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    last_status = db.Column(db.String(20), nullable=True)      # 'ok' / 'error' / 'timeout'
    last_run_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        status = "✓" if self.enabled else "✗"
        return f"<SourceState {status} {self.source_name}>"
