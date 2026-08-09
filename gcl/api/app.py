import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from gcl.api.routes import router
from gcl.config import get_settings
from gcl.loop.decision_sampler import DecisionSampler

logger = logging.getLogger(__name__)
_sampler: DecisionSampler | None = None

_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def get_sampler() -> DecisionSampler | None:
    return _sampler


async def _sampler_loop(sampler: DecisionSampler) -> None:
    while True:
        try:
            verdicts = await sampler.poll_and_audit()
            if verdicts:
                fails = sum(1 for v in verdicts if v.get("verdict") == "FAILS")
                logger.info("Sampler: %d verdicts, %d FAILS", len(verdicts), fails)
        except Exception:
            logger.exception("Decision sampler error")
        await asyncio.sleep(sampler._poll_interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _sampler
    settings = get_settings()
    if settings.ledger_url:
        _sampler = DecisionSampler(
            ledger_url=settings.ledger_url,
            ledger_token=settings.ledger_bearer_token,
            sample_rate=0.01,
            poll_interval=60,
            max_verdicts_per_poll=10,
        )
        task = asyncio.create_task(_sampler_loop(_sampler))
        logger.info("Decision sampler started (ledger=%s)", settings.ledger_url)
    else:
        task = None
        logger.info("Decision sampler disabled — no ledger_url configured")
    yield
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="Governed Cognitive Loop",
        version="0.1.0",
        description=(
            "Governed decision synthesis and falsification. Surviving decisions are "
            "signed proposals, never claims of infrastructure execution."
        ),
        lifespan=lifespan,
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

    @app.get("/api/v1/sampler/summary")
    async def sampler_summary() -> dict:
        if _sampler is None:
            return {"enabled": False}
        summary = _sampler.get_summary()
        summary["enabled"] = True
        return summary

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
