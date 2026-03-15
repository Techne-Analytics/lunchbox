from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: telemetry, scheduler — added in later tasks
    yield
    # Shutdown


app = FastAPI(title="Lunchbox", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}
