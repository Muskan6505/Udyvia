from fastapi import APIRouter, HTTPException

from ..services import registry
from ..services.validators import gstin_checksum_ok, mask_gstin

router = APIRouter(tags=["lookup"])


@router.get("/gstin/{gstin}")
def gstin(gstin: str):
    g = gstin.strip().upper()
    if not gstin_checksum_ok(g):
        raise HTTPException(422, "That doesn't look like a valid GSTIN")
    r = registry.lookup_gstin(g)
    if not r:
        raise HTTPException(404, "GSTIN not found")
    return {"gstin": mask_gstin(g), "status": r["status"], "legal_name": r["legal_name"],
            "trade_name": r["trade_name"], "address": r["principal_place_of_business"], "state": r["state"]}


@router.get("/udyam/{number}")
def udyam(number: str):
    r = registry.lookup_udyam(number.strip().upper())
    if not r:
        raise HTTPException(404, "Udyam number not found")
    return {"enterprise_name": r["enterprise_name"], "type": r["enterprise_type"],
            "activity": r["major_activity"], "state": r["state"], "city": r["city"]}
