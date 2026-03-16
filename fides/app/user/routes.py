"""Blueprint user — /app, /app/digest/<id>, /app/sources.

Tutte le route richiedono login (@login_required).
"""
import json
from pathlib import Path

from flask import render_template
from flask_login import login_required

from app import db
from app.models import Digest
from app.user import user_bp

# Categoria per ogni fonte (chiave = nome esatto in config.json)
_SOURCE_CATEGORIES = {
    "Goldman Sachs Insights - Articles":               "Asset Manager",
    "BlackRock Investment Institute":                  "Asset Manager",
    "JPMorgan Asset Management - Market Insights":     "Asset Manager",
    "PIMCO — Insights":                               "Asset Manager",
    "Morgan Stanley Investment Management — Insights": "Asset Manager",
    "Federal Reserve — Research & Notes":             "Banca Centrale",
    "ECB — Research & Publications":                  "Banca Centrale",
    "BIS — Speeches & Working Papers":                "Banca Centrale",
    "IMF — Blog & Research":                          "Organismo Internazionale",
    "World Bank — Blogs":                             "Organismo Internazionale",
    "OECD — Finance & Economics":                     "Organismo Internazionale",
}

_CATEGORY_ORDER = ["Asset Manager", "Banca Centrale", "Organismo Internazionale"]

# Badge colori Bootstrap per categoria
_CATEGORY_BADGE = {
    "Asset Manager":          "primary",
    "Banca Centrale":         "success",
    "Organismo Internazionale": "warning",
}


def _load_sources() -> list[dict]:
    """Legge config.json e restituisce lista fonti arricchita con categoria."""
    # config.json può stare in fides/config/ o nella parent blog-monitor-public/config/
    candidates = [
        Path(__file__).parent.parent.parent / "config" / "config.json",
        Path(__file__).parent.parent.parent.parent / "config" / "config.json",
    ]
    config_path = next((c for c in candidates if c.exists()), None)
    if not config_path:
        return []

    with open(config_path, encoding="utf-8") as f:
        data = json.load(f)

    sources = []
    for blog in data.get("blogs", []):
        name = blog.get("name", "")
        category = _SOURCE_CATEGORIES.get(name, "Altro")
        sources.append({
            "name": name,
            "url": blog.get("url", "#"),
            "enabled": blog.get("enabled", True),
            "category": category,
            "badge_color": _CATEGORY_BADGE.get(category, "secondary"),
        })

    def _sort_key(s):
        try:
            return _CATEGORY_ORDER.index(s["category"])
        except ValueError:
            return 99

    return sorted(sources, key=_sort_key)


# ── /app — lista digest ───────────────────────────────────────────────────────

@user_bp.route("/")
@login_required
def digest_list():
    """Lista di tutti i digest, ordine cronologico inverso."""
    digests = Digest.query.order_by(Digest.published_at.desc()).all()
    return render_template("user/digest_list.html", digests=digests)


# ── /app/digest/<id> — digest singolo ────────────────────────────────────────

@user_bp.route("/digest/<int:digest_id>")
@login_required
def digest_single(digest_id: int):
    """Digest singolo con tutti gli articoli."""
    digest = Digest.query.get_or_404(digest_id)
    articles = digest.articles.order_by(
        db.text("relevance_score DESC NULLS LAST")
    ).all()
    return render_template("user/digest_single.html", digest=digest, articles=articles)


# ── /app/sources — fonti monitorate ──────────────────────────────────────────

@user_bp.route("/sources")
@login_required
def sources():
    """Lista delle 11 fonti, lette da config.json, raggruppate per categoria."""
    sources_list = _load_sources()
    grouped: dict[str, list] = {}
    for s in sources_list:
        grouped.setdefault(s["category"], []).append(s)
    return render_template(
        "user/sources.html",
        sources=sources_list,
        grouped=grouped,
        category_order=_CATEGORY_ORDER,
        category_badge=_CATEGORY_BADGE,
    )
