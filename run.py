"""Development entry point.

Run with::

    python run.py

For production use a real WSGI server, for example::

    waitress-serve --call "app:create_app"          # Windows
    gunicorn "app:create_app()"                     # Linux/macOS
"""

from __future__ import annotations

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    app.run(host=host, port=port, debug=app.config.get("DEBUG", False))
