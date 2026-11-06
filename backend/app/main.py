from fastapi import FastAPI

from .routers import advisor, kyc, lookup, orders, quote
from .services import data

app = FastAPI(title="Udyam Digital")
app.include_router(advisor.router)
app.include_router(quote.router)
app.include_router(kyc.router)
app.include_router(orders.router)
app.include_router(lookup.router)


@app.get("/catalogue")
def catalogue():
    return list(data.catalogue().values())


@app.get("/health")
def health():
    return {"ok": True}
