"""Isolated file-backed backend for browser tests; leaves the demo state untouched."""
import os
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
os.environ["LOCAL_STATE_PATH"] = str(ROOT / "backend" / "local-data" / "browser-tests" / f"{uuid4()}.json")
os.environ["LOCAL_UI_ORIGIN"] = "http://127.0.0.1:5174"
os.environ["APP_MODE"] = "local"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("optimizer.handlers.main:app", host="127.0.0.1", port=8001)
