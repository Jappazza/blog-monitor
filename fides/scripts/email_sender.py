"""email_sender.py — Invia la notifica settimanale via Resend.

Chiamato da db_writer.finish_run() dopo che il digest è stato salvato nel DB.
Può anche essere lanciato standalone per test:

    cd fides/
    python scripts/email_sender.py --digest-id 1 --dry-run
    python scripts/email_sender.py --digest-id 1   # invio reale

Variabili d'ambiente richieste:
    RESEND_API_KEY   — API key Resend (re_...)
    EMAIL_FROM       — mittente (es. digest@fides.app)
    APP_URL          — URL base dell'app (es. https://fides.onrender.com)
"""
import argparse
import os
import sys
from pathlib import Path
from datetime import datetime

# ── Setup path ────────────────────────────────────────────────────────────────
_FIDES_ROOT = Path(__file__).parent.parent
if str(_FIDES_ROOT) not in sys.path:
    sys.path.insert(0, str(_FIDES_ROOT))

# Carica .env se le variabili non sono già impostate
if not os.environ.get("RESEND_API_KEY"):
    _env_path = _FIDES_ROOT / ".env"
    if _env_path.exists():
        with open(_env_path) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip())


# ── Template HTML email ───────────────────────────────────────────────────────

def _score_label(score: int) -> str:
    if score >= 8:
        return "🔥 Alta rilevanza"
    if score >= 6:
        return "⭐ Rilevante"
    return "✓ Utile"


def _score_color(score: int) -> str:
    if score >= 8:
        return "#198754"
    if score >= 6:
        return "#fd7e14"
    return "#6c757d"


def _build_html(digest, top_articles: list, app_url: str) -> str:
    """Compone l'HTML dell'email. Usa inline CSS per compatibilità client email."""

    digest_url = f"{app_url.rstrip('/')}/app/digest/{digest.id}"

    _months = [
        "", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
    ]
    d = digest.published_at
    date_str = f"{d.day} {_months[d.month]} {d.year}"

    # Blocchi articolo
    articles_html = ""
    for article in top_articles:
        score = article.relevance_score or 0
        starters = article.conversation_starters or []
        first_starter = starters[0] if starters else ""

        articles_html += f"""
        <tr>
          <td style="padding:0 0 24px 0;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0"
                   style="background:#f8f9fa;border-radius:8px;border-left:4px solid {_score_color(score)};">
              <tr>
                <td style="padding:16px 20px;">
                  <!-- Badge fonte + score -->
                  <table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:8px;">
                    <tr>
                      <td style="padding:2px 8px;background:{_score_color(score)};
                                 border-radius:4px;color:#fff;font-size:11px;font-weight:600;
                                 letter-spacing:.04em;">
                        {_score_label(score)} — {score}/10
                      </td>
                      {'<td style="width:8px;"></td><td style="padding:2px 8px;background:#e9ecef;border-radius:4px;color:#495057;font-size:11px;">' + article.source + '</td>' if article.source else ''}
                    </tr>
                  </table>
                  <!-- Titolo -->
                  <p style="margin:0 0 8px 0;font-size:15px;font-weight:600;color:#1a1a2e;line-height:1.4;">
                    {article.title}
                  </p>
                  <!-- Perché è rilevante -->
                  {f'<p style="margin:0 0 10px 0;font-size:13px;color:#495057;line-height:1.5;">{(article.why_relevant or "")[:200]}{"..." if len(article.why_relevant or "") > 200 else ""}</p>' if article.why_relevant else ""}
                  <!-- Spunto conversazione -->
                  {f'<p style="margin:0;padding:8px 12px;background:#fff;border-radius:4px;font-size:12px;color:#6c757d;font-style:italic;line-height:1.5;">❝ {first_starter}</p>' if first_starter else ""}
                </td>
              </tr>
            </table>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{digest.title}</title>
</head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f4f6f9;padding:40px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" border="0"
               style="max-width:600px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="background:#1a1a2e;border-radius:12px 12px 0 0;padding:28px 32px;text-align:center;">
              <p style="margin:0 0 4px 0;font-size:13px;color:rgba(255,255,255,.6);letter-spacing:.08em;text-transform:uppercase;">
                Financial Research Digest
              </p>
              <h1 style="margin:0;font-size:22px;color:#fff;font-weight:700;">
                Fides
              </h1>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="background:#fff;padding:32px;">

              <!-- Intro -->
              <p style="margin:0 0 8px 0;font-size:13px;color:#6c757d;">
                {date_str}
              </p>
              <h2 style="margin:0 0 8px 0;font-size:20px;color:#1a1a2e;font-weight:700;">
                {digest.title}
              </h2>
              <p style="margin:0 0 24px 0;font-size:14px;color:#495057;line-height:1.6;">
                Questa settimana ho trovato <strong>{digest.article_count} articoli rilevanti</strong>
                da {", ".join((digest.sources_tags or [])[:3])}
                {"e altri." if len(digest.sources_tags or []) > 3 else "."}
                Ecco i {len(top_articles)} più importanti per le tue conversazioni con i clienti.
              </p>

              <hr style="border:none;border-top:1px solid #e9ecef;margin:0 0 24px 0;">

              <!-- Articoli -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                {articles_html}
              </table>

              <!-- CTA -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td align="center" style="padding:8px 0 32px 0;">
                    <a href="{digest_url}"
                       style="display:inline-block;padding:14px 32px;background:#1a1a2e;color:#fff;
                              text-decoration:none;border-radius:8px;font-size:15px;font-weight:600;">
                      Leggi il digest completo →
                    </a>
                  </td>
                </tr>
              </table>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#f8f9fa;border-radius:0 0 12px 12px;
                       padding:20px 32px;text-align:center;">
              <p style="margin:0 0 4px 0;font-size:12px;color:#6c757d;">
                Hai ricevuto questa email perché sei registrato su
                <a href="{app_url}" style="color:#495057;">Fides</a>.
              </p>
              <p style="margin:0;font-size:12px;color:#adb5bd;">
                Financial Research Digest — ricerca istituzionale per consulenti finanziari
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""


def _build_text(digest, top_articles: list, app_url: str) -> str:
    """Versione plain text dell'email (fallback)."""
    digest_url = f"{app_url.rstrip('/')}/app/digest/{digest.id}"
    lines = [
        f"FIDES — Financial Research Digest",
        f"",
        f"{digest.title}",
        f"{digest.article_count} articoli rilevanti questa settimana.",
        f"",
        f"TOP ARTICOLI:",
        f"",
    ]
    for i, a in enumerate(top_articles, 1):
        lines.append(f"{i}. [{a.relevance_score}/10] {a.title}")
        if a.source:
            lines.append(f"   Fonte: {a.source}")
        if a.why_relevant:
            lines.append(f"   {(a.why_relevant or '')[:150]}...")
        lines.append("")

    lines += [
        f"Leggi il digest completo:",
        f"{digest_url}",
        f"",
        f"---",
        f"Fides — {app_url}",
    ]
    return "\n".join(lines)


# ── Funzione principale ───────────────────────────────────────────────────────

def send_weekly_notification(
    digest_id: int,
    dry_run: bool = False,
) -> dict:
    """Invia la notifica settimanale a tutti gli utenti attivi.

    Args:
        digest_id:  ID del Digest appena creato
        dry_run:    Se True, stampa l'email senza inviarla (per test)

    Returns:
        Dict con risultati: {"sent": int, "failed": int, "errors": list}
    """
    from app import create_app, db
    from app.models import Digest, User

    app = create_app()
    with app.app_context():
        digest = Digest.query.get(digest_id)
        if not digest:
            raise ValueError(f"Digest id={digest_id} non trovato")

        # Top 3 articoli per score
        top_articles = (
            digest.articles
            .order_by(db.text("relevance_score DESC NULLS LAST"))
            .limit(3)
            .all()
        )

        if not top_articles:
            print(f"  Nessun articolo nel digest {digest_id}, email non inviata.")
            return {"sent": 0, "failed": 0, "errors": []}

        app_url = os.environ.get("APP_URL", "https://fides.onrender.com")
        from_addr = os.environ.get("EMAIL_FROM", "digest@fides.app")
        api_key = os.environ.get("RESEND_API_KEY", "")

        html_body = _build_html(digest, top_articles, app_url)
        text_body = _build_text(digest, top_articles, app_url)

        if dry_run:
            print("=" * 60)
            print("DRY RUN — email NON inviata")
            print(f"From:    {from_addr}")
            print(f"Subject: Nuovo digest Fides — {digest.title}")
            print(f"Top articoli: {[a.title[:50] for a in top_articles]}")
            print("=" * 60)
            return {"sent": 0, "failed": 0, "errors": [], "dry_run": True}

        if not api_key:
            print("  ⚠️  RESEND_API_KEY non impostata — email non inviate.")
            return {"sent": 0, "failed": 0, "errors": ["RESEND_API_KEY mancante"]}

        import resend
        resend.api_key = api_key

        users = User.query.filter_by(is_active=True).all()
        sent = 0
        failed = 0
        errors = []

        for user in users:
            try:
                resend.Emails.send({
                    "from": from_addr,
                    "to": user.email,
                    "subject": f"📊 Nuovo digest Fides — {digest.title}",
                    "html": html_body,
                    "text": text_body,
                })
                sent += 1
                print(f"  ✓ Email inviata a {user.email}")
            except Exception as e:
                failed += 1
                errors.append(f"{user.email}: {e}")
                print(f"  ✗ Errore per {user.email}: {e}")

        print(f"  Email: {sent} inviate, {failed} fallite.")
        return {"sent": sent, "failed": failed, "errors": errors}


# ── Entry point standalone ────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Invia notifica digest via Resend")
    parser.add_argument("--digest-id", type=int, required=True, help="ID del digest")
    parser.add_argument("--dry-run", action="store_true", help="Simula senza inviare")
    args = parser.parse_args()

    result = send_weekly_notification(args.digest_id, dry_run=args.dry_run)
    print(result)
