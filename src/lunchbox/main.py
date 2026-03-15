from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from lunchbox.api.feeds import router as feeds_router
from lunchbox.auth.router import router as auth_router
from lunchbox.config import settings
from lunchbox.db import engine
from lunchbox.scheduler.jobs import start_scheduler, stop_scheduler
from lunchbox.telemetry.setup import setup_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_telemetry(app=app, engine=engine)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Lunchbox", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware, secret_key=settings.secret_key, max_age=30 * 24 * 3600
)
app.include_router(auth_router)
app.include_router(feeds_router)


@app.get("/health")
def health():
    return {"status": "ok"}
