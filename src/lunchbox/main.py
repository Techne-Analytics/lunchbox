from contextlib import asynccontextmanager

from fastapi import FastAPI

from lunchbox.api.feeds import router as feeds_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: telemetry, scheduler — added in later tasks
    yield
    # Shutdown


app = FastAPI(title="Lunchbox", lifespan=lifespan)
app.include_router(feeds_router)


@app.get("/health")
def health():
    return {"status": "ok"}
