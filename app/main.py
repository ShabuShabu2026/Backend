from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router
from app.config import Settings
from app.data.loader import load_metadata
from app.routes.analyses import router as analyses_router
from app.routes.config import router as config_router
from app.routes.weights import router as weights_router
from app.settings import CORS_ORIGINS


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.data = load_metadata(app.state.settings.raster_paths)
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(CORS_ORIGINS),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.include_router(analyses_router)
    app.include_router(config_router)
    app.include_router(weights_router)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"success": False, "error": {
            "code": "INVALID_REQUEST", "message": "Invalid request parameters."}})

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code = {400: "INVALID_REQUEST", 404: "ANALYSIS_NOT_FOUND",
                503: "DATA_NOT_READY"}.get(exc.status_code, "INTERNAL_ERROR")
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content={"success": False, "error": exc.detail})
        return JSONResponse(status_code=exc.status_code, content={"success": False, "error": {
            "code": code, "message": str(exc.detail)}})
    return app


app = create_app()
