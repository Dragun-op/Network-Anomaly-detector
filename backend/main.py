from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.config import get_settings
from app.db import init_db
from app.replay import replay_worker
from app.ws import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    replay_worker.start(app.state)
    yield
    replay_worker.stop(app.state)


app = FastAPI(title="Network-Traffix API", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(ws_router)


@app.get("/")
async def root():
    return {"message": "Network-Traffix API — see /docs"}
