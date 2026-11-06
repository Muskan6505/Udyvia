import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .privacy import logging_filter, policy, retention
from .routers import advisor, demo, kyc, lookup, orders, privacy, quote, voice
from .services import data

logging_filter.install()


@asynccontextmanager
async def lifespan(_app):
    """Deletes data whose retention period has ended, even if nobody touches the service."""
    async def loop():
        while True:
            await asyncio.sleep(policy.PURGE_INTERVAL_SECONDS)
            await asyncio.to_thread(retention.purge_all)
    kyc.sweep_orphans(min_age_seconds=0)     # on startup nothing in memory owns any uploaded file, so remove them all
    task = asyncio.create_task(loop())
    yield
    task.cancel()


app = FastAPI(title="Udyam Digital", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(advisor.router)
app.include_router(quote.router)
app.include_router(kyc.router)
app.include_router(orders.router)
app.include_router(demo.router)
app.include_router(privacy.router)
app.include_router(voice.router)
app.include_router(lookup.router)


@app.get("/catalogue")
def catalogue():
    return list(data.catalogue().values())


@app.get("/health")
def health():
    return {"ok": True}
