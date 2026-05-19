from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from router.geo import router as geo_router
from service.inspector import reconcile_interrupted_runs


load_dotenv()

app = FastAPI(title="GEO Platform Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(geo_router)


@app.on_event("startup")
async def reconcile_diagnostic_runs_on_startup() -> None:
    reconcile_interrupted_runs()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
