from __future__ import annotations

from service.queryset_matrix_client import QuerySetMatrixClient


async def generate_queryset(brand_config: dict, run: dict) -> dict:
    source = run.get("queryset_source") or "matrix_api_v1"
    if source == "matrix_api_v1":
        return await QuerySetMatrixClient().generate(brand_config, run)
    raise RuntimeError(f"Unsupported queryset_source: {source}")
