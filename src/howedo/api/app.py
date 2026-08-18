from __future__ import annotations

from fastapi import FastAPI

from .models import ContinuityCheckRequest, ContinuityCheckResponse, HealthResponse
from .service import check_continuity


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
        return check_continuity(request)

    return app


app = create_app()
