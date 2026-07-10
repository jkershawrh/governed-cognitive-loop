import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from gcl.api.routes import router

_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Governed Cognitive Loop",
        version="0.1.0",
        description="LLM-MPC with evidence-based constraint classification and hypothesis falsification before commit.",
    )

    origins = os.environ.get("GCL_CORS_ORIGINS", "http://localhost:3000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    async def health() -> dict:
        return {"status": "ok"}

    app.include_router(router)

    if _FRONTEND_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=_FRONTEND_DIR / "assets"), name="assets")

        @app.get("/{path:path}")
        async def spa_fallback(path: str) -> FileResponse:
            file = _FRONTEND_DIR / path
            if file.is_file():
                return FileResponse(file)
            return FileResponse(_FRONTEND_DIR / "index.html")

    return app
