from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .models import (
    ContinuityCheckRequest,
    ContinuityCheckResponse,
    HealthResponse,
    RecoveryCheckRequest,
    RecoveryCheckResponse,
)
from .service import check_continuity, check_recovery


def create_app() -> FastAPI:
    app = FastAPI(
        title="HOWEDO",
        version="v1",
        description="Deployable API boundary for the HOWEDO continuity kernel.",
    )

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
