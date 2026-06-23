from __future__ import annotations

import asyncio
import logging

from dotenv import load_dotenv
from fastapi import Request
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from router.geo import router as geo_router
from service.inspector import recover_active_runs_after_restart, run_diagnostic_job


load_dotenv()
logger = logging.getLogger(__name__)

app = FastAPI(title="GEO Platform Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(geo_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    endpoint = f"{request.method} {request.url.path}"
    logger.exception("unhandled_backend_exception", extra={"endpoint": endpoint, "stage": "unhandled_exception"})
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal backend error.",
            "error_code": "internal_backend_error",
            "endpoint": endpoint,
            "stage": "unhandled_exception",
            "exception_type": type(exc).__name__,
        },
    )


@app.on_event("startup")
async def reconcile_diagnostic_runs_on_startup() -> None:
    for run_id in recover_active_runs_after_restart():
        task = asyncio.create_task(run_diagnostic_job(run_id))
        task.add_done_callback(_log_background_task_result)


def _log_background_task_result(task: asyncio.Task) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        logger.info("diagnostic_recovery_task_cancelled")
    except Exception:
        logger.exception("diagnostic_recovery_task_failed")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
