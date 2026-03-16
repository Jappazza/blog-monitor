"""Blueprint auth — /register, /login, /logout.

Gestisce l'autenticazione degli utenti normali.
L'area admin usa un meccanismo separato (session['admin_logged_in']).
"""
from datetime import datetime, timezone

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.exceptions import abort

from app import db
from app.auth import auth_bp
from app.models import User


# ── /register ─────────────────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Registrazione nuovo utente."""
    if current_user.is_authenticated:
        return redirect(url_for("user.digest_list"))

    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        # Validazione
        if not email or "@" not in email:
            error = "Inserisci un indirizzo email valido."
        elif len(password) < 8:
            error = "La password deve essere di almeno 8 caratteri."
        elif password != password_confirm:
            error = "Le password non coincidono."
        elif User.query.filter_by(email=email).first():
            error = "Questa email è già registrata. Accedi direttamente."
        else:
            # Crea utente
            user = User(email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            # Login automatico dopo registrazione
            login_user(user, remember=True)
            flash("Benvenuto su Fides! Il tuo account è stato creato.", "success")
            return redirect(url_for("user.digest_list"))

        if error:
            flash(error, "danger")

    return render_template("auth/register.html")


# ── /login ────────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Login utente esistente."""
    if current_user.is_authenticated:
        return redirect(url_for("user.digest_list"))

    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            error = "Email o password errati. Riprova."
        elif not user.is_active:
            error = "Il tuo account è stato disattivato. Contatta il supporto."
        else:
            # Aggiorna last_login
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()

            login_user(user, remember=True)
            flash("Accesso effettuato.", "success")

            # Rispetta il parametro ?next= per redirect post-login
            next_page = request.args.get("next")
            if next_page and next_page.startswith("/"):   # sicurezza: solo path interni
                return redirect(next_page)
            return redirect(url_for("user.digest_list"))

        if error:
            flash(error, "danger")

    return render_template("auth/login.html")


# ── /logout ───────────────────────────────────────────────────────────────────

@auth_bp.route("/logout")
@login_required
def logout():
    """Termina la sessione utente."""
    logout_user()
    flash("Hai effettuato il logout.", "info")
    return redirect(url_for("auth.login"))


# ── /privacy ──────────────────────────────────────────────────────────────────

@auth_bp.route("/privacy")
def privacy():
    """Privacy policy minimale (GDPR)."""
    return render_template("auth/privacy.html")
