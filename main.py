from __future__ import annotations

import os
import sys

import uvicorn
from app.main import app as dishlist_app

# Re-export the FastAPI app so `uvicorn main:app` works for production runs.
app = dishlist_app


def _should_reload() -> bool:
    """Return whether live reload should be enabled for development."""

    raw = os.getenv("DISHLIST_RELOAD")
    if raw is None:
        return True
    return raw.lower() in {"1", "true", "yes", "on"}


def main() -> None:
    """Convenience entry point for running the FastAPI development server."""

    reload_enabled = _should_reload()
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=reload_enabled)
    except PermissionError:
        # Some environments (e.g., sandboxes/CI) block file system watchers that
        # uvicorn uses for reload. Fall back to a no-reload server instead of
        # hanging on startup.
        if not reload_enabled:
            raise
        print(
            "Live reload is not permitted; starting without reload. "
            "Set DISHLIST_RELOAD=0 to skip this fallback.",
            file=sys.stderr,
        )
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
