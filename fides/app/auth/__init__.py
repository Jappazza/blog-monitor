from flask import Blueprint

auth_bp = Blueprint("auth", __name__, url_prefix="")

from app.auth import routes  # noqa: E402, F401 — importa routes per registrare le view
