from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.models.schemas import ApiMessage
from backend.routers import bot, config, coordinates, logs, stats


app = FastAPI(title="COC Auto Farm API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
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
