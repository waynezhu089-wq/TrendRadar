from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import feedback, health, market, research, today, watchlist, daily, plan_assistant, tibo, videos, commissions
from app.db.database import initialize_database
from app.api.v1 import source_connections
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse

@asynccontextmanager
async def lifespan(app):
    initialize_database()
    yield

app = FastAPI(title="Dream Intelligence", lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def safe_source_validation(request, error):
    if request.url.path.startswith('/api/v1/source-connections'):
        return JSONResponse(status_code=422,content={'detail':'SOURCE_CONFIG_INVALID'})
    return await request_validation_exception_handler(request,error)

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
app.include_router(source_connections.router, prefix="/api/v1")
