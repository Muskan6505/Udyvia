from fastapi import APIRouter

from ..privacy import policy

router = APIRouter(prefix="/privacy", tags=["privacy"])


@router.get("/policy")
def get_policy():
    """What we keep, for how long, and who else sees it. Same constants the cleanup job enforces."""
    return {
        "retention": {"kyc_documents_and_results_hours": policy.KYC_HOURS, "chat_answers_hours": policy.ADVISOR_HOURS,
                      "unordered_quotes_hours": policy.QUOTE_HOURS, "orders_days": policy.ORDER_DAYS},
        "third_parties": policy.THIRD_PARTIES,
        "controls": ["Consent is required before any upload", "Withdraw at any time to delete uploads and results",
                     "Identifiers are masked in the UI, logs and audit trail", "Documents are read on our own server"],
    }
