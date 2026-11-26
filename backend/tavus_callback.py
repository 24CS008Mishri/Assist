"""Dedicated public ingress for the Tavus evidence tool."""
from fastapi import FastAPI

from backend.routers.live_assistant import tavus_tool

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.add_api_route("/api/live-assistant/tavus-tool", tavus_tool, methods=["POST"])
