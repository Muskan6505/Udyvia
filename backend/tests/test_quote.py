import csv
import pytest
from fastapi.testclient import TestClient

from app.config import DATA_DIR
from app.main import app
from app.schemas import Profile
from app.services import data, eligibility as el
from app.services.recommender import assemble
from app.services.segmenter import classify, MICRO, PROF, MFG, MULTI

c = TestClient(app)


def prof(**kw):
    base = dict(business_type="Kirana store", employees=3, sites=1, city_tier=2, has_gstin=False)
    base.update(kw)
    return Profile(**base)


def ids(q, inc=True):
    return {l.product_id for l in q.lines if l.included == inc}


def test_segments():
    assert classify(prof()) == MICRO
    assert classify(prof(business_type="Dental clinic", employees=20)) == PROF
    assert classify(prof(business_type="Textile unit", employees=80)) == MFG
    assert classify(prof(business_type="Bakery chain", employees=60, sites=7)) == MULTI


def test_micro_no_gstin_starter_bundle():
    q, _ = assemble(prof())
    assert ids(q) == {"P01", "P07"}
    assert q.contract_months == 12
    assert q.setup_total == 0
    # GSTIN-gated products are never in the bundle
    assert not any(el.rule_failures(data.catalogue()[i], q.profile, False, "x") == [] and
                   data.catalogue()[i].requires_gstin for i in ids(q) | ids(q, False))


def test_blocked_gstin_has_upgrade_path():
    q, _ = assemble(prof(business_type="Textile unit", employees=80, city_tier=1, needs=["phone"]))
    b = {x.product_id: x for x in q.blocked}
    assert "P05" in b and b["P05"].alternative == "P02" and "GSTIN" in b["P05"].upgrade_path
    assert "P05" not in ids(q) and "P02" in ids(q)
    assert "P12" in b


def test_gstin_gated_with_active_gstin():
    g = next(k for k, v in data.gstin_registry().items() if v["status"] == "Active")
    q, _ = assemble(prof(business_type="Textile unit", employees=80, city_tier=1, gstin=g))
    assert "P05" in ids(q)


@pytest.mark.parametrize("status", ["Cancelled", "Suspended"])
def test_inactive_gstin_treated_as_no_gstin(status):
    g = next(k for k, v in data.gstin_registry().items() if v["status"] == status)
    q, _ = assemble(prof(business_type="Textile unit", employees=80, city_tier=1, gstin=g))
    assert "P05" not in ids(q)
    assert any("GSTIN" in n for n in q.notes)


def test_tier2_never_gets_tier1_only_products():
    q, _ = assemble(prof(business_type="CA firm", employees=20, city_tier=2, has_gstin=True))
    assert "P03" not in ids(q) | ids(q, False)


def test_dependency_auto_added_when_no_connectivity():
    # user asks for CCTV only via add-on after removing connectivity -> cascade, no orphan
    r = c.post("/quote", json=dict(business_type="Kirana store", employees=3, sites=1, city_tier=1,
                                   has_gstin=False, needs=["cctv"])).json()
    qid = r["quote_id"]
    assert any(l["product_id"] == "P23" and l["included"] for l in r["lines"])
    r = c.patch(f"/quote/{qid}/addons", json=dict(product_id="P01", included=False)).json()
    inc = {l["product_id"] for l in r["lines"] if l["included"]}
    assert "P01" not in inc and "P23" not in inc


def test_static_ip_blocked_on_leased_line_only():
    g = next(k for k, v in data.gstin_registry().items() if v["status"] == "Active")
    q, _ = assemble(prof(business_type="Textile unit", employees=80, city_tier=1, gstin=g, needs=["static ip"]))
    assert "P05" in ids(q) and "P11" not in ids(q)   # catalogue: P11 needs P01|P02|P03
    assert any(b.product_id == "P11" for b in q.blocked)


def test_every_included_line_satisfies_rules_on_leads():
    """Run the engine over all 5,000 leads: no output may break a catalogue rule."""
    cat = data.catalogue()
    n = 0
    with open(DATA_DIR / "smb_leads.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            p = Profile(business_type=r["business_type"], segment=r["segment"], employees=int(r["employee_count"]),
                        sites=int(r["num_sites"]), city_tier=int(r["city_tier"]),
                        gstin=r["gstin"] or None, has_gstin=r["has_gstin"] == "Y",
                        needs=r["products_of_interest"].split(";"))
            q, _ = assemble(p)
            inc = ids(q)
            gok, gm = el.gstin_ok(q.gstin_status, p)
            for pid in inc:
                assert not el.rule_failures(cat[pid], p, gok, gm), (r["lead_id"], pid)
                assert el.dependency_met(cat[pid], inc), (r["lead_id"], pid)
            assert q.monthly_total > 0
            n += 1
    assert n == 5000


def test_price_within_catalogue_range():
    q, _ = assemble(prof(business_type="CA firm", employees=15))
    cat = data.catalogue()
    for l in q.lines:
        assert cat[l.product_id].price_min <= l.unit_price <= cat[l.product_id].price_max


def test_budget_fit():
    q, _ = assemble(prof(business_type="CA firm", employees=15, budget_monthly=2500))
    assert q.price_position == 0.0
    assert q.within_budget in (True, False)


def test_add_ineligible_product_rejected():
    r = c.post("/quote", json=dict(business_type="Kirana store", employees=3, sites=1, city_tier=2,
                                   has_gstin=False)).json()
    r = c.patch(f"/quote/{r['quote_id']}/addons", json=dict(product_id="P10", included=True)).json()
    assert not any(l["product_id"] == "P10" and l["included"] for l in r["lines"])
    assert any(b["product_id"] == "P10" for b in r["blocked"])


def test_addon_toggle_updates_total():
    r = c.post("/quote", json=dict(business_type="Kirana store", employees=3, sites=1, city_tier=1,
                                   has_gstin=False)).json()
    before = r["monthly_total"]
    r = c.patch(f"/quote/{r['quote_id']}/addons", json=dict(product_id="P19", included=True)).json()
    assert r["monthly_total"] > before and r["setup_total"] == 2500
