"""
FastAPI application factory.

This is the HTTP entry point — the only thing deployment infrastructure
(Cloud Run, a VPS behind nginx, a Docker container, etc.) needs to know
about is "there's an ASGI app that speaks HTTP on some port". Nothing here
assumes a specific hosting provider.

Startup/shutdown lifecycle (DB connection, PTB Application init/start,
webhook registration) is handled through FastAPI's `lifespan`, so resources
are acquired once per process and released cleanly, rather than per-request.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from telegram.ext import Application

from app.core.config import AppConfig
from app.core.logging import get_logger
from app.database.connection import Database
from app.webhook.routes import router

logger = get_logger(__name__)


def create_app(config: AppConfig, telegram_application: Application, database: Database) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Connecting here (rather than in main.py) guarantees this runs on
        # the same event loop the ASGI server serves requests on — aiosqlite
        # connections are bound to the loop they were opened on.
        await database.connect()
        await telegram_application.initialize()
        await telegram_application.start()

        if config.webhook.public_url:
            full_url = config.webhook.public_url.rstrip("/") + config.webhook.path
            await telegram_application.bot.set_webhook(
                url=full_url,
                secret_token=config.webhook.secret_token,
            )
            logger.info("webhook_registered", extra={"url": full_url})
        else:
            logger.info("webhook_registration_skipped", extra={"reason": "WEBHOOK_URL not set"})

        logger.info("app_ready", extra={"ai_enabled": config.ai.enabled})
        try:
            yield
        finally:
            await telegram_application.stop()
            await telegram_application.shutdown()
            await database.close()
            logger.info("app_shutdown_complete")

    app = FastAPI(title="telegram-ai-bot", lifespan=lifespan)
    app.state.config = config
    app.state.telegram_application = telegram_application
    app.include_router(router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "ai_enabled": config.ai.enabled}

    @app.exception_handler(Exception)
    async def catch_all(request: Request, exc: Exception) -> JSONResponse:
        # Last-resort safety net: no route in this app should reach here
        # (routes.py already catches what it expects), but if something
        # unexpected slips through, never leak the exception to the caller.
        logger.error("unhandled_http_exception", exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "internal error"})

    return app
