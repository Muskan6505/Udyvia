"""Demo the KYC validator without any UI:   python kyc_cli.py K06      |      python kyc_cli.py --all"""
import sys

from app.config import DATA_DIR
from app.services.kyc_decision import run_kyc
from app.services.ocr import DOC_TYPES

ICON = {"fix": "✋", "review": "🔎", "restrict": "⛔", "info": "ℹ️ "}


def show(k: str) -> None:
    paths = {t: (DATA_DIR / "kyc_documents" / f"{k}_{t}.png") for t in DOC_TYPES}
    r = run_kyc({t: p for t, p in paths.items() if p.exists()})
    print(f"\n{k}: {r.decision}   (GST-gated products {'allowed' if r.gst_products_allowed else 'blocked'})   {r.verified}")
    for f in r.findings:
        print(f"   {ICON[f.severity]} {f.code:<28} {f.message}")


if __name__ == "__main__":
    ids = [f"K{i:02d}" for i in range(1, 13)] if "--all" in sys.argv or len(sys.argv) < 2 else sys.argv[1:]
    for k in ids:
        show(k)
