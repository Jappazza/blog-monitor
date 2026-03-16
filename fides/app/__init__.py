"""App factory per Fides.

Usa il pattern Application Factory per supportare:
- ambienti multipli (dev / test / production)
- Flask-Migrate senza import circolari
- blueprint registrati separatamente
"""
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from dotenv import load_dotenv

load_dotenv()

# Estensioni inizializzate senza app (pattern factory)
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()


def create_app() -> Flask:
    """Crea e configura l'istanza Flask."""
    app = Flask(__name__)

    # ── Configurazione ──────────────────────────────────────────────────────
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///fides_dev.db"
    )
    # Supabase/PostgreSQL usa "postgres://" (legacy); SQLAlchemy richiede "postgresql://"
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgres://"):
        app.config["SQLALCHEMY_DATABASE_URI"] = app.config["SQLALCHEMY_DATABASE_URI"].replace(
            "postgres://", "postgresql://", 1
        )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # Sessione persistente 7 giorni (remember_me)
    app.config["REMEMBER_COOKIE_DURATION"] = 60 * 60 * 24 * 7

    # ── Estensioni ──────────────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"           # redirect se non autenticato
    login_manager.login_message = "Accedi per continuare."
    login_manager.login_message_category = "warning"

    # ── User loader (Flask-Login) ────────────────────────────────────────────
    from app.models import User  # import locale per evitare circolarità

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(user_id)

    # ── Blueprint ────────────────────────────────────────────────────────────
    from app.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.user import user_bp
    app.register_blueprint(user_bp)

    from app.admin import admin_bp
    app.register_blueprint(admin_bp)

    # ── Root redirect ────────────────────────────────────────────────────────
    from flask import redirect, url_for

    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    return app
