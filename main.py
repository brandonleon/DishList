from __future__ import annotations

import uvicorn


def main() -> None:
    """Convenience entry point for running the FastAPI development server."""

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
