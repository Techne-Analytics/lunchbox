from starlette.middleware.sessions import SessionMiddleware

from lunchbox.api.router import api_router
from lunchbox.auth.router import router as auth_router
from lunchbox.config import settings
from lunchbox.db import engine
from lunchbox.telemetry.setup import instrument_app, setup_telemetry
from lunchbox.web.router import router as web_router

# Module-level telemetry init (Vercel may not dispatch ASGI lifespan events)
setup_telemetry(engine=engine)

from fastapi import FastAPI, Request  # noqa: E402 — must be after telemetry init
from fastapi.responses import PlainTextResponse  # noqa: E402
import traceback  # noqa: E402

app = FastAPI(title="Lunchbox")
app.add_middleware(
    SessionMiddleware, secret_key=settings.secret_key, max_age=30 * 24 * 3600
)

# Instrument FastAPI after app creation
instrument_app(app)


@app.exception_handler(Exception)
async def debug_exception_handler(request: Request, exc: Exception):
    """Temporary: return full traceback for debugging deployment."""
    return PlainTextResponse(
        f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}",
        status_code=500,
    )


app.include_router(auth_router)
app.include_router(api_router)
app.include_router(web_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/debug")
def debug() -> dict:
    """Temporary debug endpoint — remove after deployment verified."""
    import os
    from pathlib import Path

    web_dir = Path(__file__).parent / "web"
    templates_dir = web_dir / "templates"
    return {
        "cwd": os.getcwd(),
        "file": str(Path(__file__)),
        "web_dir_exists": web_dir.exists(),
        "templates_dir_exists": templates_dir.exists(),
        "templates_files": [f.name for f in templates_dir.iterdir()]
        if templates_dir.exists()
        else [],
        "static_dir": str(web_dir / "static"),
        "static_exists": (web_dir / "static").exists(),
    }
