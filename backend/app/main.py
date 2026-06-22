from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import (
    admin,
    agents,
    artifacts,
    auth,
    avatars,
    cron_jobs,
    friends,
    health,
    html_templates,
    mcp_servers,
    media,
    models,
    oauth,
    page_templates,
    pricing,
    profile,
    rag,
    ratings,
    runs,
    system,
    templates,
    users,
    wallet,
    workflows,
    works,
)
from app.core.logging import configure_logging
from app.core.settings import get_settings

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="AgentWorks API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(profile.router)
app.include_router(agents.router)
app.include_router(templates.router)
app.include_router(html_templates.router)
app.include_router(page_templates.router)
app.include_router(avatars.router)
app.include_router(artifacts.router)
app.include_router(artifacts.public_router)
app.include_router(models.router)
app.include_router(works.router)
app.include_router(runs.router)
app.include_router(ratings.router)
app.include_router(workflows.router)
app.include_router(cron_jobs.router)
app.include_router(rag.router)
app.include_router(media.router)
app.include_router(wallet.router)
app.include_router(friends.router)
app.include_router(oauth.router)
app.include_router(pricing.router)
app.include_router(mcp_servers.router)
app.include_router(admin.router)
app.include_router(system.router)

os.makedirs(settings.media_root, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_root), name="media")
