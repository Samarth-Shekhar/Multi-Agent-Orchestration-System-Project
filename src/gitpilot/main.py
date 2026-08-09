"""GitPilot main FastAPI entrypoint and CLI runner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from gitpilot import __version__
from gitpilot.api.routes import router as api_router
from gitpilot.config import get_settings

# Path setup for templates and static files
PACKAGE_DIR = Path(__file__).parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"

app = FastAPI(
    title="GitPilot",
    description="Multi-Agent GitHub Issue to Pull Request Orchestrator",
    version=__version__,
)

# Mount static files and templates
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

if TEMPLATES_DIR.exists():
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.auto_reload = True
    templates.env.cache = {}
else:
    templates = None


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    """Serve web dashboard."""
    if templates:
        response = templates.TemplateResponse(request=request, name="index.html")
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response
    return HTMLResponse("<h1>GitPilot API is running</h1><p>Dashboard templates missing</p>")


app.include_router(api_router)


def main():
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="GitPilot Multi-Agent Orchestrator")
    parser.add_argument("--host", default="0.0.0.0", help="Host to listen on")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--demo", action="store_true", help="Run free demo workflow and exit")
    args = parser.parse_args()

    if args.demo:
        from gitpilot.demo import run_demo
        sys.exit(run_demo())

    settings = get_settings()
    uvicorn.run(
        "gitpilot.main:app",
        host=args.host or settings.host,
        port=args.port or settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
