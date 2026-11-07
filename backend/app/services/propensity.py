"""Which unfinished leads to call first.

A small logistic regression trained on the 5,000 historical leads (data/smb_leads.csv): "of leads that
looked like this and had got this far, how many went on to activate?". It is deliberately simple so a
salesperson can be told why a lead ranks where it does: every feature's pull is shown in plain words.

Inputs are things we know about a live lead: how far they got, business type, city tier, size, GSTIN,
current internet. Rules-based blockers (KYC problems, over budget...) are shown beside the score but
are not part of it, because the history has no record of them."""
from __future__ import annotations

import csv
import math
from functools import lru_cache

import numpy as np

from ..config import DATA_DIR

STAGES = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete"]   # Activated rows count as KYC complete
FEATURES = ["stage", "business_type", "city_tier", "employees", "sites", "has_gstin", "internet", "source"]
LABELS = {"stage": "How far they got", "business_type": "Business type", "city_tier": "City", "employees": "Team size",
          "sites": "Locations", "has_gstin": "GSTIN", "internet": "Current internet", "source": "Lead source"}
LAMBDA = 2.0


def _emp(n: int) -> str:
    return "1-5 people" if n <= 5 else "6-15 people" if n <= 15 else "16-50 people" if n <= 50 else "51+ people"


def _sites(n: int) -> str:
    return "1 location" if n <= 1 else "2-5 locations" if n <= 5 else "6+ locations"


def features(*, stage: str | None, business_type: str | None, city_tier: int | None, employees: int | None,
             sites: int | None, has_gstin: bool | None, internet: str | None, source: str = "Website form") -> dict:
    return {"stage": stage, "business_type": business_type or None,
            "city_tier": None if city_tier is None else f"Tier {city_tier}",
            "employees": None if employees is None else _emp(employees),
            "sites": None if sites is None else _sites(sites),
            "has_gstin": None if has_gstin is None else ("Has GSTIN" if has_gstin else "No GSTIN yet"),
            "internet": internet or None, "source": source}


def _leads() -> list[tuple[dict, int, int]]:
    """(features without a stage, furthest stage index reached, activated?)."""
    out = []
    with open(DATA_DIR / "smb_leads.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            won = r["outcome"] == "Activated"
            far = len(STAGES) - 1 if won else STAGES.index(r["stage_reached"])
            out.append((features(stage=None, business_type=r["business_type"], city_tier=int(r["city_tier"]),
                                 employees=int(r["employee_count"]), sites=int(r["num_sites"]),
                                 has_gstin=r["has_gstin"] == "Y", internet=r["current_internet"] or None,
                                 source=r["lead_source"]), far, int(won)))
    return out


def _expand(leads) -> list[tuple[dict, int]]:
    """One example per stage a lead passed through: 'sitting at this stage, did they eventually activate?'.
    A lead that activated counts as a success at every stage it went through, a lead that dropped counts as
    a failure only at the stages it reached. Otherwise early-stage leads would look hopeless."""
    return [({**feat, "stage": STAGES[s]}, won) for feat, far, won in leads for s in range(far + 1)]


def _rows() -> list[tuple[dict, int]]:
    return _expand(_leads())


def _fit(rows: list[tuple[dict, int]]) -> dict:
    vocab = {f: sorted({x[0][f] for x in rows if x[0][f] is not None}) for f in FEATURES}
    cols = [(f, v) for f in FEATURES for v in vocab[f]]
    idx = {c: i for i, c in enumerate(cols)}
    X = np.zeros((len(rows), len(cols) + 1))
    X[:, -1] = 1.0
    y = np.array([r[1] for r in rows], dtype=float)
    for i, (feat, _) in enumerate(rows):
        for f in FEATURES:
            if feat[f] is not None:
                X[i, idx[(f, feat[f])]] = 1.0
    w = np.zeros(X.shape[1])
    reg = np.eye(X.shape[1]) * LAMBDA
    reg[-1, -1] = 0.0                                   # the intercept is not shrunk
    for _ in range(30):                                 # Newton / IRLS with an L2 penalty
        p = 1 / (1 + np.exp(-X @ w))
        g = X.T @ (p - y) + reg @ w
        H = (X * (p * (1 - p))[:, None]).T @ X + reg
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-7:
            break
    # Re-centre each feature on its average value, so "unknown" means "average" and every feature's
    # contribution reads as "better or worse than a typical lead".
    contrib: dict[str, dict[str, float]] = {}
    bias = float(w[-1])
    for f in FEATURES:
        vals = [r[0][f] for r in rows if r[0][f] is not None]
        mean = sum(w[idx[(f, v)]] for v in vals) / len(vals)
        contrib[f] = {v: float(w[idx[(f, v)]] - mean) for v in vocab[f]}
        bias += float(mean)
    raw_stage = dict(contrib["stage"])
    m = dict(bias=bias, contrib=contrib)
    # Calibrate per stage: shift each stage's effect until the average predicted chance matches the
    # activation rate actually seen at that stage (averaging in log-odds space alone under-states it).
    for st in STAGES:
        grp = [r for r in rows if r[0]["stage"] == st]
        if not grp:
            continue
        target = sum(r[1] for r in grp) / len(grp)
        lo, hi = -6.0, 6.0
        for _ in range(40):
            mid = (lo + hi) / 2
            m["contrib"]["stage"][st] = raw_stage[st] + mid
            avg = sum(score(r[0], m)["probability"] for r in grp[:: max(1, len(grp) // 400)]) / len(grp[:: max(1, len(grp) // 400)])
            lo, hi = (mid, hi) if avg < target else (lo, mid)
        m["contrib"]["stage"][st] = raw_stage[st] + (lo + hi) / 2
    return m


@lru_cache(maxsize=1)
def model() -> dict:
    return _fit(_rows())


def score(feat: dict, m: dict | None = None) -> dict:
    m = m or model()
    z = m["bias"]
    parts = []
    for f in FEATURES:
        v = feat.get(f)
        c = m["contrib"][f].get(v, 0.0) if v is not None else 0.0
        z += c
        if v is not None and f != "source":
            parts.append((c, f, v))
    p = 1 / (1 + math.exp(-z))
    parts.sort(key=lambda t: -abs(t[0]))
    factors = [dict(feature=LABELS[f], value=v, effect=round(c, 2), direction="up" if c > 0 else "down")
               for c, f, v in parts[:4] if abs(c) >= 0.05]
    return dict(probability=round(p, 4), factors=factors)


def band(p: float) -> str:
    return "Hot" if p >= 0.30 else "Warm" if p >= 0.12 else "Cold"


# ---------- honesty check: does it rank better than "just look at the stage"? ----------
def auc(scores: list[float], labels: list[int]) -> float:
    pairs = sorted(zip(scores, labels))
    rank_sum, i = 0.0, 0
    while i < len(pairs):
        j = i
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        rank_sum += (i + 1 + j) / 2 * sum(l for _, l in pairs[i:j])
        i = j
    n1 = sum(labels)
    n0 = len(labels) - n1
    return (rank_sum - n1 * (n1 + 1) / 2) / (n1 * n0)


def evaluate(seed: int = 7) -> dict:
    """Hold out 20% of leads (never splitting one lead across train and test) and, within each stage,
    check how well the model ranks eventual winners above losers. A stage-only score cannot rank leads
    that are at the same stage (AUC 0.5), so this is the part that has to earn its keep."""
    leads = _leads()
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(leads))
    cut = int(len(leads) * 0.8)
    m = _fit(_expand([leads[i] for i in order[:cut]]))
    test = [leads[i] for i in order[cut:]]
    per_stage = {}
    for si, name in enumerate(STAGES):
        ex = [(feat, won) for feat, far, won in test if far >= si]
        y = [w for _, w in ex]
        if 0 < sum(y) < len(y):
            per_stage[name] = dict(n=len(y), activation_rate=round(sum(y) / len(y), 3),
                                   auc=round(auc([score({**f, "stage": name}, m)["probability"] for f, _ in ex], y), 3))
    return dict(train_leads=cut, test_leads=len(test), by_stage=per_stage)
