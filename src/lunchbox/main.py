from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from lunchbox.api.router import api_router
from lunchbox.auth.router import router as auth_router
from lunchbox.config import settings
from lunchbox.web.router import router as web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: telemetry, scheduler — added in later tasks
    yield
    # Shutdown


app = FastAPI(title="Lunchbox", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware, secret_key=settings.secret_key, max_age=30 * 24 * 3600
)

app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "web" / "static")),
    name="static",
)

app.include_router(auth_router)
app.include_router(api_router)
app.include_router(web_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
