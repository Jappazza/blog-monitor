"""Entry point per l'applicazione Fides.

Uso locale:
    python run.py

Uso produzione (Render/gunicorn):
    gunicorn run:app
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
