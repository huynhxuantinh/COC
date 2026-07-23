from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.models.schemas import ApiMessage
from backend.routers import bot, config, coordinates, logs, stats


app = FastAPI(title="COC Auto Farm API", version="1.0.0")


def cors_origins() -> list[str]:
    raw = os.getenv("COC_CORS_ORIGINS", "")
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or ["http://127.0.0.1:5173", "http://localhost:5173"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bot.router)
app.include_router(config.router)
app.include_router(coordinates.router)
app.include_router(logs.router)
app.include_router(stats.router)


@app.get("/api/health", response_model=ApiMessage)
def health() -> ApiMessage:
    return ApiMessage(message="OK")
