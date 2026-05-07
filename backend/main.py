from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import os
from dotenv import load_dotenv
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Load environment variables from .env file
load_dotenv()

from services.db import init_db
from routers import config, testcases, history, ai, upload


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="AzDO TestCase Manager API",
    version="1.0.0",
    description="Backend for the Azure DevOps Test Case Manager — proxy, AI generation, history.",
    lifespan=lifespan,
)

# Register rate limiter
app.state.limiter = ai.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config.router,     prefix="/api/config",    tags=["Configuration"])
app.include_router(testcases.router,  prefix="/api/testcases", tags=["Test Cases"])
app.include_router(upload.router,     prefix="/api/upload",    tags=["Upload"])
app.include_router(history.router,    prefix="/api/history",   tags=["History"])
app.include_router(ai.router,         prefix="/api/ai",        tags=["AI Generation"])

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

# Serve frontend static assets (CSS, JS)
css_dir = os.path.join(FRONTEND_DIR, "css")
js_dir = os.path.join(FRONTEND_DIR, "js")
if os.path.isdir(css_dir):
    app.mount("/css", StaticFiles(directory=css_dir), name="css")
if os.path.isdir(js_dir):
    app.mount("/js", StaticFiles(directory=js_dir), name="js")

@app.get("/", include_in_schema=False)
def serve_frontend():
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "AzDO TestCase Manager API is running. See /docs for API reference."}

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
