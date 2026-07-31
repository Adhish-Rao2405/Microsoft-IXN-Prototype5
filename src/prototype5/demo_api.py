"""FastAPI boundary for the Prototype 5 integrated demonstrator."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .demo_runtime import build_demo_service
from .demo_service import (
    DemoApplicationService,
    DemoStatusResponse,
    DomainNotAvailableError,
    TypedCommandApiRequest,
)
from .hybrid_inference_router import HybridGovernanceResultV1


def create_demo_app(
    service: DemoApplicationService,
    *,
    frontend_dist: Path | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Prototype 5 Zero-Trust Robotics Demonstrator",
        version="2.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/api/v1/status", response_model=DemoStatusResponse)
    def status() -> DemoStatusResponse:
        return service.status()

    @app.post(
        "/api/v1/governance/typed",
        response_model=HybridGovernanceResultV1,
    )
    def submit_typed(
        request: TypedCommandApiRequest,
    ) -> HybridGovernanceResultV1:
        try:
            return service.submit_typed(request)
        except DomainNotAvailableError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": str(exc)},
            ) from exc

    if frontend_dist is not None and frontend_dist.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=frontend_dist, html=True),
            name="frontend",
        )
    else:
        @app.get("/", include_in_schema=False)
        def root() -> RedirectResponse:
            return RedirectResponse(url="/api/docs")

    return app


def create_runtime_app() -> FastAPI:
    repo_root = Path(__file__).resolve().parents[2]
    return create_demo_app(
        build_demo_service(repo_root),
        frontend_dist=repo_root / "frontend" / "dist",
    )
