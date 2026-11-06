import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import advisor, demo, kyc, lookup, orders, quote
from .services import data

app = FastAPI(title="Udyam Digital")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(advisor.router)
app.include_router(quote.router)
app.include_router(kyc.router)
app.include_router(orders.router)
app.include_router(demo.router)
app.include_router(lookup.router)


@app.get("/catalogue")
def catalogue():
    return list(data.catalogue().values())


@app.get("/health")
def health():
    return {"ok": True}
