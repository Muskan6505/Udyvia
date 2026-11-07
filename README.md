# Udyvia

Rules engine and quote API (first slice). LLM advisor, KYC, tracker and frontend come next.

    cd backend && pip install -r requirements.txt
    python -m pytest -q
    uvicorn app.main:app --reload     # POST /quote, GET /quote/{id}, PATCH /quote/{id}/addons

Engine: `services/segmenter.py` -> `eligibility.py` (tier, size, GSTIN status, dependencies)
-> `recommender.py` (segment templates, quantities) -> `pricing.py` (price inside catalogue min/max).

## Accounts, saved progress and the back-office view

- **Accounts (SQLite).** `POST /auth/register|login|logout`, `GET /auth/me`, `DELETE /auth/account`. Passwords are scrypt-hashed; the session is an httpOnly cookie. The database file is `backend/var/udyvia.db` (override with `UDYVIA_DB`).
- **Resume.** Progress is written to the account as the person moves (advisor answers, quote add-ons, KYC decision, order). `POST /me/resume` rebuilds the working state and says which screen to open, so signing in on any browser, even after a server restart, continues where they stopped. Uploaded documents are deliberately not resumable (24-hour deletion), so a person who stopped mid-KYC is asked to upload again.
- **Back-office.** Open `http://localhost:3000/office`. Create a staff login with `python -m app.staff EMAIL PASSWORD` (or set `BACKOFFICE_EMAIL` and `BACKOFFICE_PASSWORD`). It lists unfinished leads who agreed to be called, ranked by a **propensity score**, with the reasons it ranks where it does, why the lead stalled, a suggested next step, and call-outcome notes.
- **Sample leads for a demo.** `python -m app.seed_demo` adds 14 unfinished leads built from real dropped rows in `data/smb_leads.csv` (made-up names and numbers, flagged `sample`); `python -m app.seed_demo --clear` removes them.
- **The score** (`backend/app/services/propensity.py`) is a regularised logistic regression on the 5,000 historical leads: "of leads like this, sitting at this stage, how many activated?". Stage-by-stage averages are calibrated to the history. On 1,000 held-out leads it ranks eventual winners above losers within a stage with AUC 0.60-0.70 (0.5 is a coin toss), so it is a modest aid for ordering a call list, not a verdict. The screen shows this table.
