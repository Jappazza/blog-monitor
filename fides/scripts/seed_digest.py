"""seed_digest.py — Importa un file markdown di blog_monitor_v2.py nel database Fides.

Uso:
    cd fides/
    python scripts/seed_digest.py ../output/blog_report_20260305_171406.md

Il parser riconosce il formato prodotto da blog_monitor_v2.py:

    # Blog Monitor Report
    **Data generazione:** 2026-03-05 17:14
    **Articoli analizzati:** 24

    ### 🔥 Titolo articolo - Nome Fonte

    **Rilevanza:** 9/10
    **Data pubblicazione:** Thu, 08 Jan 2026 ...
    **Link:** [testo](url)

    #### Descrizione
    ...

    #### Perché può essere importante per te
    ...

    #### I punti chiave
    - bullet 1
    - bullet 2

    #### Spunti di conversazione con il cliente
    - spunto 1
    - spunto 2
"""
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Aggiunge la root del progetto (fides/) al path per poter importare `app`
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

# Se DATABASE_URL non è impostata, create_app() usa SQLite di default

from app import create_app, db
from app.models import Article, Digest


# ── Helpers per il parsing ────────────────────────────────────────────────────

def _extract_section(text: str, heading: str) -> str:
    """Estrae il testo di una sezione `#### Heading` fino alla sezione successiva."""
    pattern = rf"#### {re.escape(heading)}\n(.*?)(?=\n####|\Z)"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""


def _extract_bullets(text: str, heading: str) -> list[str]:
    """Estrae i bullet point di una sezione come lista di stringhe."""
    raw = _extract_section(text, heading)
    bullets = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("- "):
            bullets.append(line[2:].strip())
    return bullets


def _parse_date(raw: str) -> datetime | None:
    """Prova diversi formati data tipici dell'output dello script."""
    raw = raw.strip()
    formats = [
        "%a, %d %b %Y %H:%M:%S %Z",   # Thu, 08 Jan 2026 08:00:00 GMT
        "%a, %d %b %Y %H:%M:%S %z",
        "%m/%d/%Y",                     # 02/25/2026
        "%Y-%m-%d",
        "%d %B %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _extract_url(raw_link: str) -> str:
    """Estrae l'URL da `[testo](url)` oppure restituisce il raw se è già un URL."""
    m = re.search(r"\(([^)]+)\)", raw_link)
    if m:
        return m.group(1)
    return raw_link.strip()


_URL_TO_SOURCE = {
    "goldmansachs.com":   "Goldman Sachs",
    "blackrock.com":      "BlackRock",
    "jpmorgan.com":       "JPMorgan",
    "federalreserve.gov": "Federal Reserve",
    "ecb.europa.eu":      "ECB",
    "pimco.com":          "PIMCO",
    "morganstanley.com":  "Morgan Stanley",
    "imf.org":            "IMF",
    "worldbank.org":      "World Bank",
    "bis.org":            "BIS",
    "oecd.org":           "OECD",
}


def _source_from_url(url: str | None) -> str | None:
    """Deduce il nome della fonte dall'URL se il titolo non lo contiene."""
    if not url:
        return None
    for domain, name in _URL_TO_SOURCE.items():
        if domain in url:
            return name
    return None


def _extract_source_from_title(title: str) -> tuple[str, str]:
    """Separa 'Titolo articolo - Nome Fonte' in (titolo, fonte).

    Usa l'ultimo ' - ' come separatore (alcuni titoli contengono ' - ' al loro interno).
    """
    # Rimuovi l'emoji 🔥 iniziale se presente
    title = re.sub(r"^[^\w]*", "", title).strip()
    # Cerca ' - ' partendo da destra
    idx = title.rfind(" - ")
    if idx > 0:
        return title[:idx].strip(), title[idx + 3:].strip()
    # Prova anche ' — '
    idx = title.rfind(" — ")
    if idx > 0:
        return title[:idx].strip(), title[idx + 3:].strip()
    return title, ""


# ── Parser principale ─────────────────────────────────────────────────────────

def parse_markdown(md_path: Path) -> dict:
    """Parsa il markdown e restituisce un dict con metadata e lista articoli."""
    text = md_path.read_text(encoding="utf-8")

    # ── Header del report ────────────────────────────────────────────────────
    gen_date_m = re.search(r"\*\*Data generazione:\*\*\s*(.+)", text)
    gen_date_raw = gen_date_m.group(1).strip() if gen_date_m else ""
    try:
        generated_at = datetime.strptime(gen_date_raw, "%Y-%m-%d %H:%M")
    except ValueError:
        generated_at = datetime.now(timezone.utc)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)

    articles_total_m = re.search(r"\*\*Articoli analizzati:\*\*\s*(\d+)", text)
    articles_total = int(articles_total_m.group(1)) if articles_total_m else 0

    # ── Articoli: ogni sezione inizia con `### ` ──────────────────────────────
    # Splittiamo il testo in blocchi per ogni articolo
    blocks = re.split(r"\n### ", text)
    # Il primo blocco è l'header del report, lo saltiamo
    article_blocks = blocks[1:]

    articles = []
    sources_seen = set()

    for block in article_blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue

        # Prima riga = titolo (con emoji e fonte)
        raw_title = lines[0].strip()
        article_title, source = _extract_source_from_title(raw_title)
        if source:
            sources_seen.add(source)

        block_text = "\n".join(lines[1:])

        # Rilevanza
        rel_m = re.search(r"\*\*Rilevanza:\*\*\s*(\d+)/10", block_text)
        relevance = int(rel_m.group(1)) if rel_m else None

        # Data pubblicazione
        pub_m = re.search(r"\*\*Data pubblicazione:\*\*\s*(.+)", block_text)
        published_date = None
        if pub_m:
            parsed = _parse_date(pub_m.group(1))
            if parsed:
                published_date = parsed.date()

        # Link / URL
        link_m = re.search(r"\*\*Link:\*\*\s*(\S+.*)", block_text)
        url = _extract_url(link_m.group(1).strip()) if link_m else None

        # Sezioni testuali
        description = _extract_section(block_text, "Descrizione")
        why_relevant = _extract_section(block_text, "Perché può essere importante per te")
        key_points = _extract_bullets(block_text, "I punti chiave")
        conversation_starters = _extract_bullets(block_text, "Spunti di conversazione con il cliente")

        # Usa la descrizione come why_relevant se why_relevant è vuoto
        if not why_relevant and description:
            why_relevant = description

        # Fallback: deduce la fonte dall'URL se non è nel titolo
        if not source:
            source = _source_from_url(url) or "Sconosciuta"
        if source:
            sources_seen.add(source)

        articles.append({
            "title": article_title or raw_title,
            "source": source,
            "relevance_score": relevance,
            "why_relevant": why_relevant,
            "key_points": key_points,
            "conversation_starters": conversation_starters,
            "original_url": url,
            "published_date": published_date,
        })

    return {
        "generated_at": generated_at,
        "articles_total": articles_total,
        "articles": articles,
        "sources_seen": sorted(sources_seen),
    }


# ── Inserimento nel DB ────────────────────────────────────────────────────────

def seed(md_path: Path, app) -> None:
    """Inserisce il digest nel database."""
    print(f"Parsing {md_path.name} ...")
    data = parse_markdown(md_path)

    print(f"  Trovati {len(data['articles'])} articoli da: {', '.join(data['sources_seen'])}")

    with app.app_context():
        # Crea le tabelle se non esistono (utile in sviluppo senza flask db upgrade)
        db.create_all()

        # Controlla se esiste già un digest con la stessa data
        existing = Digest.query.filter(
            Digest.published_at == data["generated_at"]
        ).first()
        if existing:
            print(f"  ⚠️  Digest già presente (id={existing.id}). Salto.")
            return

        # Titolo automatico
        locale_months = [
            "", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
            "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"
        ]
        d = data["generated_at"]
        title = f"Digest — {d.day} {locale_months[d.month]} {d.year}"

        # Summary: prime 3 fonti viste
        top_sources = data["sources_seen"][:3]
        summary = (
            f"Ricerca da {', '.join(top_sources)}"
            + (f" e altri" if len(data["sources_seen"]) > 3 else "")
            + f". {len(data['articles'])} articoli analizzati."
        )

        digest = Digest(
            title=title,
            published_at=data["generated_at"],
            article_count=len(data["articles"]),
            summary=summary,
            sources_tags=data["sources_seen"],
        )
        db.session.add(digest)
        db.session.flush()  # ottieni digest.id prima di commit

        for a in data["articles"]:
            article = Article(
                digest_id=digest.id,
                title=a["title"],
                source=a["source"],
                relevance_score=a["relevance_score"],
                why_relevant=a["why_relevant"],
                key_points=a["key_points"],
                conversation_starters=a["conversation_starters"],
                original_url=a["original_url"],
                published_date=a["published_date"],
            )
            db.session.add(article)

        db.session.commit()
        print(f"  ✓ Digest inserito (id={digest.id}) con {len(data['articles'])} articoli.")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/seed_digest.py <path/al/blog_report.md>")
        sys.exit(1)

    md_path = Path(sys.argv[1])
    if not md_path.exists():
        print(f"Errore: file non trovato: {md_path}")
        sys.exit(1)

    flask_app = create_app()
    seed(md_path, flask_app)
