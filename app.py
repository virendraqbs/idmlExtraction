"""
app.py — Application factory and entry point.

All heavy lifting lives in controllers/, services/, models/, utils/.
This file wires them together and exposes create_app() for testing.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from config import config
from controllers import auth_router, jobs_router, NotAuthenticatedException
from database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)


def create_app() -> FastAPI:
    """Application factory.  Call this to get a configured FastAPI instance."""
    app = FastAPI(title="CL Pipeline", docs_url=None, redoc_url=None)

    app.add_middleware(
        SessionMiddleware,
        secret_key=config.SECRET_KEY,
        max_age=14 * 24 * 60 * 60,
    )

    config.init_dirs()
    init_db()

    static_dir = config.BASE_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(auth_router)
    app.include_router(jobs_router)

    @app.exception_handler(NotAuthenticatedException)
    async def _redirect_to_login(request: Request, exc: NotAuthenticatedException):
        return RedirectResponse(url="/login", status_code=303)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=config.PORT,
        reload=config.DEBUG,
    )
