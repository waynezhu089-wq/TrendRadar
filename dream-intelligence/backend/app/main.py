from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import feedback, health, market, research, today, watchlist, daily, plan_assistant, tibo, videos, commissions
from app.db.database import initialize_database

@asynccontextmanager
async def lifespan(app):
    initialize_database()
    yield

app = FastAPI(title="Dream Intelligence", lifespan=lifespan)
app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"])
app.include_router(health.router, prefix="/api/v1")
app.include_router(today.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(watchlist.router, prefix="/api/v1")
app.include_router(market.router, prefix="/api/v1")
app.include_router(research.router, prefix="/api/v1")
app.include_router(daily.router, prefix="/api/v1")
app.include_router(plan_assistant.router, prefix="/api/v1")
app.include_router(tibo.router, prefix="/api/v1")
app.include_router(videos.router, prefix="/api/v1")
app.include_router(commissions.router, prefix="/api/v1")
