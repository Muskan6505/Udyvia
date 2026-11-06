# Udyam Digital

Rules engine and quote API (first slice). LLM advisor, KYC, tracker and frontend come next.

    cd backend && pip install -r requirements.txt
    python -m pytest -q
    uvicorn app.main:app --reload     # POST /quote, GET /quote/{id}, PATCH /quote/{id}/addons

Engine: `services/segmenter.py` -> `eligibility.py` (tier, size, GSTIN status, dependencies)
-> `recommender.py` (segment templates, quantities) -> `pricing.py` (price inside catalogue min/max).
