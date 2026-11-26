"""Optional FastAPI transport for one loopback-only synthetic classroom process.

A boot profile is not user authentication. Never expose this adapter to other users.
"""

from contextlib import asynccontextmanager
import json
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from host import Host

PUBLIC = {"ask", "stage", "inspect", "review", "recover"}
CODES = {"forbidden": 403, "not_available": 404, "invalid_request": 400, "rate_limited": 429,
         "dependency_unavailable": 503, "review_conflict": 409, "inconsistent": 409,
         "rejected": 409, "not_runnable": 409}


@asynccontextmanager
async def lifespan(app):
    profile = os.environ.get("LAB_PROFILE", "support")
    if profile not in {"support", "reviewer"}:
        raise ValueError("unknown classroom profile")
    app.state.profile = profile
    app.state.host = Host(Path(os.environ.get("LAB_STATE_DIR", "/state")),
                          build=os.environ.get("LAB_BUILD", "v1"),
                          outage=os.environ.get("LAB_OUTAGE") == "1")
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.post("/lab/{operation}")
async def call(operation: str, request: Request):
    if operation not in PUBLIC:
        return JSONResponse({"status": "not_available"}, status_code=404)
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        return JSONResponse({"status": "invalid_request"}, status_code=415)
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > 4096:
            return JSONResponse({"status": "invalid_request"}, status_code=413)
        data.extend(chunk)
    try:
        payload = json.loads(data)
    except (ValueError, RecursionError):
        return JSONResponse({"status": "invalid_request"}, status_code=400)
    # Synchronous local call, no await inside the effect boundary. One worker only.
    result = app.state.host.dispatch(app.state.profile, operation, payload)
    visible = {key: result[key] for key in ("status", "binding", "evidence", "receipt", "draft") if key in result}
    return JSONResponse(visible, status_code=CODES.get(result["status"], 200))
