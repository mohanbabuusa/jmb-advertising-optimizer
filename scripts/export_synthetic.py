"""Export deterministic source fixtures without modifying live local state."""
import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
from optimizer.adapters.local.seed import generate

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--end-date", type=date.fromisoformat, default=datetime.now(timezone.utc).date() - timedelta(days=1))
args = parser.parse_args()
state = generate(args.end_date)
destination = ROOT / "data" / "synthetic"
destination.mkdir(parents=True, exist_ok=True)
for product, history in state["histories"].items():
    (destination / f"{product}.json").write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
(destination / "manifest.json").write_text(json.dumps(state["manifest"], indent=2) + "\n", encoding="utf-8")
print(f"Exported 450 observations to {destination}")
