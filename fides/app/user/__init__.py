from flask import Blueprint

user_bp = Blueprint("user", __name__, url_prefix="/app")

from app.user import routes  # noqa: E402, F401
