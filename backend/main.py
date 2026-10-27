"""InGame Studio - Main Server Entrypoint.

Exports the FastAPI application instance from backend.app.
Supports running via:
  uvicorn backend.main:app --port 8000
  uvicorn backend.app:app --port 8000
"""

from backend.app import app

__all__ = ["app"]
