"""Dedicated public ingress for the Tavus evidence tool."""
from contextlib import asynccontextmanager
import logging
import os

from anyio import to_thread
from fastapi import FastAPI

from backend.routers.live_assistant import tavus_tool
from backend.services.rag_service import get_embeddings


@asynccontextmanager
async def lifespan(_app):
    if os.getenv("TAVUS_PAL_ID", "").strip():
        try:
            await to_thread.run_sync(lambda: get_embeddings().embed_query("curriculum review"))
        except Exception as exc:
            logging.getLogger(__name__).warning("Vaani embedding warmup failed (%s)", type(exc).__name__)
    yield


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.add_api_route("/api/live-assistant/tavus-tool", tavus_tool, methods=["POST"])
