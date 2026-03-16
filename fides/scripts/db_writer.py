"""db_writer.py — Salva i risultati di blog_monitor_v2.py nel database Fides.

Usato da blog_monitor_v2.py al termine di ogni run:

    from fides.scripts.db_writer import start_run, finish_run

    run_id = start_run()
    # ... esecuzione script ...
    finish_run(run_id, all_analyses, source_errors)

Può anche essere usato standalone per importare report markdown storici
(vedi seed_digest.py per questo caso d'uso).

Requisiti:
- DATABASE_URL deve essere impostata nell'ambiente (o nel .env di fides/)
- La cartella fides/ deve essere nel sys.path, oppure questo file deve essere
  eseguito da dentro fides/
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Setup path — permette l'import di `app` sia da fides/ che da blog-monitor-public/ ──
_FIDES_ROOT = Path(__file__).parent.parent          # fides/
if str(_FIDES_ROOT) not in sys.path:
    sys.path.insert(0, str(_FIDES_ROOT))

# Carica .env di fides/ se DATABASE_URL non è già impostata
if not os.environ.get("DATABASE_URL"):
    _env_path = _FIDES_ROOT / ".env"
    if _env_path.exists():
        with open(_env_path) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip())

from app import create_app, db
from app.models import Article, Digest, RunLog, SourceState

# Istanza Flask — creata una sola volta per processo
_flask_app = None


def _get_app():
    global _flask_app
    if _flask_app is None:
        _flask_app = create_app()
    return _flask_app


def _now():
    return datetime.now(timezone.utc)


# ── API pubblica ──────────────────────────────────────────────────────────────

def start_run() -> int:
    """Crea un RunLog con status 'running' e ritorna il suo ID.

    Da chiamare all'inizio di BlogMonitorV2.run().
    """
    app = _get_app()
    with app.app_context():
        db.create_all()  # no-op se le tabelle esistono già
        run_log = RunLog(
            started_at=_now(),
            status=RunLog.STATUS_RUNNING,
        )
        db.session.add(run_log)
        db.session.commit()
        return run_log.id


def finish_run(
    run_log_id: int,
    analyses: list[dict],
    source_errors: Optional[dict] = None,
    min_score: int = 6,
) -> Optional[int]:
    """Salva il Digest + Articles nel DB e chiude il RunLog.

    Args:
        run_log_id:     ID del RunLog creato da start_run()
        analyses:       Lista di dict prodotti da analyze_post_with_ai()
                        Ogni dict ha: title, link, date, blog_name,
                        relevance_score, descrizione, rilevanza,
                        punti_chiave, spunti_conversazione
        source_errors:  Dict opzionale {blog_name: "messaggio errore"}
        min_score:      Score minimo per includere un articolo nel digest (default 6)

    Returns:
        ID del Digest creato, oppure None se non ci sono articoli rilevanti.
    """
    app = _get_app()
    with app.app_context():
        run_log = RunLog.query.get(run_log_id)
        if not run_log:
            raise ValueError(f"RunLog id={run_log_id} non trovato")

        # Filtra articoli rilevanti
        relevant = [a for a in analyses if a.get("relevance_score", 0) >= min_score]
        relevant.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        digest_id = None

        if relevant:
            # Titolo con data italiana
            _months = [
                "", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
                "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
            ]
            now = _now()
            title = f"Digest — {now.day} {_months[now.month]} {now.year}"

            # Fonti uniche presenti nel digest
            sources_seen = sorted({
                a.get("blog_name", "").strip()
                for a in relevant
                if a.get("blog_name")
            })

            # Summary: prime 3 fonti + contatore
            summary = (
                "Ricerca da " + ", ".join(sources_seen[:3])
                + (" e altri" if len(sources_seen) > 3 else "")
                + f". {len(relevant)} articoli analizzati."
            )

            digest = Digest(
                title=title,
                published_at=now,
                article_count=len(relevant),
                summary=summary,
                sources_tags=sources_seen,
            )
            db.session.add(digest)
            db.session.flush()  # ottieni digest.id prima del commit

            for a in relevant:
                # Mappa i campi dall'output AI ai campi del modello
                article = Article(
                    digest_id=digest.id,
                    title=a.get("title", ""),
                    source=a.get("blog_name", ""),
                    relevance_score=a.get("relevance_score"),
                    why_relevant=a.get("rilevanza") or a.get("descrizione"),
                    key_points=a.get("punti_chiave") or [],
                    conversation_starters=a.get("spunti_conversazione") or [],
                    original_url=a.get("link"),
                    published_date=_parse_date(a.get("date", "")),
                )
                db.session.add(article)

            digest_id = digest.id

        # Aggiorna RunLog
        status = RunLog.STATUS_SUCCESS
        if source_errors:
            status = (
                RunLog.STATUS_PARTIAL if relevant else RunLog.STATUS_ERROR
            )

        run_log.completed_at = _now()
        run_log.status = status
        run_log.articles_found = len(relevant)
        run_log.digest_id = digest_id
        run_log.error_details = source_errors or None

        db.session.commit()

        # Aggiorna SourceState per ogni fonte elaborata
        _update_source_states(analyses, source_errors or {})

        # Invia notifica email se il digest è stato creato (successo o parziale)
        if digest_id and status in (RunLog.STATUS_SUCCESS, RunLog.STATUS_PARTIAL):
            try:
                from scripts.email_sender import send_weekly_notification
                send_weekly_notification(digest_id)
            except Exception as _e:
                print(f"  ⚠️  Email non inviata: {_e}")

        return digest_id


def _update_source_states(analyses: list[dict], source_errors: dict) -> None:
    """Aggiorna la tabella source_states per ogni fonte del run."""
    app = _get_app()
    with app.app_context():
        # Fonti con almeno un articolo analizzato (successo)
        sources_ok = {a.get("blog_name") for a in analyses if a.get("blog_name")}

        all_sources = sources_ok | set(source_errors.keys())

        for source_name in all_sources:
            if not source_name:
                continue
            state = SourceState.query.filter_by(source_name=source_name).first()
            if not state:
                state = SourceState(source_name=source_name, enabled=True)
                db.session.add(state)

            state.last_run_at = _now()
            if source_name in source_errors:
                error_msg = str(source_errors[source_name]).lower()
                state.last_status = (
                    SourceState.STATUS_TIMEOUT
                    if "timeout" in error_msg
                    else SourceState.STATUS_ERROR
                )
            else:
                state.last_status = SourceState.STATUS_OK

        db.session.commit()


def _parse_date(raw: str):
    """Prova a parsare la data dell'articolo restituendo un oggetto date o None."""
    from datetime import date
    import re

    if not raw or raw == "N/A":
        return None
    raw = raw.strip()

    formats = [
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%m/%d/%Y",
        "%Y-%m-%d",
        "%d %B %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None
