from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from lunchbox.auth.router import router as auth_router
from lunchbox.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: telemetry, scheduler — added in later tasks
    yield
    # Shutdown


app = FastAPI(title="Lunchbox", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware, secret_key=settings.secret_key, max_age=30 * 24 * 3600
)
app.include_router(auth_router)


@app.get("/health")
def health():
    return {"status": "ok"}
