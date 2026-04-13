from starlette.middleware.sessions import SessionMiddleware

from lunchbox.api.router import api_router
from lunchbox.auth.router import router as auth_router
from lunchbox.config import settings
from lunchbox.db import engine
from lunchbox.telemetry.setup import instrument_app, setup_telemetry
from lunchbox.web.router import router as web_router

# Module-level telemetry init (Vercel may not dispatch ASGI lifespan events)
setup_telemetry(engine=engine)

from fastapi import FastAPI  # noqa: E402 — must be after telemetry init

app = FastAPI(title="Lunchbox")
app.add_middleware(
    SessionMiddleware, secret_key=settings.secret_key, max_age=30 * 24 * 3600
)

# Instrument FastAPI after app creation
instrument_app(app)

app.include_router(auth_router)
app.include_router(api_router)
app.include_router(web_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
