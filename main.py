from __future__ import annotations

import uvicorn
from app.main import app as dishlist_app

# Re-export the FastAPI app so `uvicorn main:app` works for production runs.
app = dishlist_app


def main() -> None:
    """Convenience entry point for running the FastAPI development server."""

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
