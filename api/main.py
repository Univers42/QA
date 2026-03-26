"""
Prismatica QA API — FastAPI application.

Mounts three routers:
    /tests      CRUD for test definitions
    /tests/run  Execute tests (REST + WebSocket)
    /results    Query execution history

Start with:
    uvicorn api.main:app --reload --port 8000

Interactive docs available at:
    http://localhost:8000/docs     (Swagger UI)
    http://localhost:8000/redoc    (ReDoc)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import results, run, tests

app = FastAPI(
    title="Prismatica QA API",
    version="3.0.0",
    description=(
        "QA Hub API for Prismatica / ft_transcendence. "
        "Test definitions, execution, and result history."
    ),
)

# Allow the React dashboard (Vite dev server) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3003",  # Alternative dashboard port
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(tests.router, prefix="/tests", tags=["Tests"])
app.include_router(run.router, prefix="/tests", tags=["Run"])
app.include_router(results.router, prefix="/results", tags=["Results"])


@app.get("/", tags=["Health"])
async def health():
    """Health check — confirms the API is running."""
    return {
        "status": "ok",
        "service": "prismatica-qa-api",
        "version": "3.0.0",
    }
