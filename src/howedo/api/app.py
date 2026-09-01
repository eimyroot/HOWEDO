from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from .cockpit import render_cockpit
from .models import (
    ContinuityCheckRequest,
    ContinuityCheckResponse,
    HealthResponse,
    RecoveryCheckRequest,
    RecoveryCheckResponse,
)
from .service import check_continuity, check_recovery

_COCKPIT_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; "
        "style-src 'unsafe-inline'; "
        "script-src 'unsafe-inline'; "
        "connect-src 'self'; "
        "img-src 'self' data:; "
        "base-uri 'none'; "
        "form-action 'none'; "
        "frame-ancestors 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


def create_app() -> FastAPI:
    app = FastAPI(
        title="HOWEDO",
        version="v1",
        description="Deployable API and cockpit boundary for the HOWEDO continuity kernel.",
    )

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/cockpit", response_class=HTMLResponse, include_in_schema=False)
    def cockpit() -> HTMLResponse:
        return HTMLResponse(content=render_cockpit(), headers=_COCKPIT_HEADERS)

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["system"],
    )
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="howedo",
        )

    @app.get(
        "/ready",
        response_model=HealthResponse,
        tags=["system"],
    )
    def ready() -> HealthResponse:
        return HealthResponse(
            status="ready",
            service="howedo",
        )

    @app.post(
        "/v1/continuity/check",
        response_model=ContinuityCheckResponse,
        tags=["continuity"],
    )
    def continuity_check(
        request: ContinuityCheckRequest,
    ) -> ContinuityCheckResponse:
        try:
            return check_continuity(request)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post(
        "/v1/recovery/check",
        response_model=RecoveryCheckResponse,
        tags=["recovery"],
    )
    def recovery_check(
        request: RecoveryCheckRequest,
    ) -> RecoveryCheckResponse:
        try:
            return check_recovery(request)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app


app = create_app()
