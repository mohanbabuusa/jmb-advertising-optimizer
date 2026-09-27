"""Local-only FastAPI composition root. No cloud credentials, clients, or calls."""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from optimizer.adapters.local.reasoner import FixtureReasoner
from optimizer.adapters.local.seed import generate
from optimizer.adapters.local.store import JsonStore
from optimizer.application.service import AppError, Optimizer, audit
from optimizer.domain.forecast import forecast
from optimizer.domain.schemas import DecisionRequest, EmptyRequest

ROOT = Path(__file__).resolve().parents[3]


def create_app(state_path: Path | None = None, clock=None) -> FastAPI:
    if os.getenv("APP_MODE", "local") != "local":
        raise RuntimeError("Phase 1 supports APP_MODE=local only. AWS and Bedrock are not implemented.")
    now = clock() if clock else datetime.now(timezone.utc)
    store = JsonStore(state_path or Path(os.getenv("LOCAL_STATE_PATH", ROOT / "local-data" / "state.json")))
    initial = generate(now.date() - timedelta(days=1))
    for product in initial["products"]:
        audit(initial, "SIMULATION_INITIALIZED", product["productId"], None,
              {"datasetVersion": initial["manifest"]["version"]}, now.isoformat())
    store.initialize(initial)
    service = Optimizer(store, FixtureReasoner(), clock)
    ui_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
    if os.getenv("LOCAL_UI_ORIGIN"):
        ui_origins.append(os.environ["LOCAL_UI_ORIGIN"])
    app = FastAPI(title="JMB Advertising — Local Simulation", version="0.1.0")
    app.state.service = service
    app.add_middleware(CORSMiddleware, allow_origins=ui_origins,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Idempotency-Key"])

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        # Fixed local demo identity, loopback-only run instructions, and same-origin write protection.
        origin = request.headers.get("origin")
        if request.method == "POST" and origin and origin not in ui_origins + ["http://localhost:8000", "http://127.0.0.1:8000"]:
            return JSONResponse(status_code=403, content={"error": {"code": "ORIGIN_DENIED", "message": "Local origin required."}})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(AppError)
    async def app_error(_request, error):
        return JSONResponse(status_code=error.status, content={"error": {"code": error.code,
                            "message": error.message, "requestId": str(uuid4()), "retryable": False}})

    def key(value: str) -> str:
        try:
            return str(UUID(value))
        except ValueError:
            raise AppError(400, "INVALID_KEY", "Idempotency-Key must be a UUID.")

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "local", "reasoner": "FixtureReasoner", "simulation": True}

    @app.get("/v1/products")
    def products():
        return {"items": store.read()["products"]}

    @app.get("/v1/products/{pid}/history")
    def history(pid: str):
        state = store.read()
        service.product(state, pid)
        return state["histories"][pid]

    @app.get("/v1/products/{pid}/forecast")
    def prediction(pid: str):
        return forecast(history(pid))

    @app.get("/v1/products/{pid}/campaign")
    def campaign(pid: str):
        state = store.read()
        service.product(state, pid)
        return state["campaigns"][pid]

    @app.post("/v1/products/{pid}/recommendations", status_code=201)
    def recommend(pid: str, body: EmptyRequest, idempotency_key: str = Header()):
        return service.generate(pid, key(idempotency_key))

    @app.get("/v1/recommendations/{rid}")
    def recommendation(rid: str):
        return service.get_recommendation(rid)

    @app.post("/v1/recommendations/{rid}/decision")
    def decision(rid: str, body: DecisionRequest, idempotency_key: str = Header()):
        return service.decide(rid, body.model_dump(), key(idempotency_key))

    @app.get("/v1/products/{pid}/recommendations")
    def recommendations(pid: str):
        state = store.read()
        service.product(state, pid)
        rows = [service.effective(r) for r in state["recommendations"].values() if r["productId"] == pid]
        return {"items": sorted(rows, key=lambda r: r["createdAt"], reverse=True), "nextCursor": None}

    @app.get("/v1/audit")
    def history_audit(productId: str | None = None, recommendationId: str | None = None,
                      limit: int = Query(default=25, ge=1, le=100), before: str | None = None):
        if productId and recommendationId:
            raise AppError(400, "INVALID_FILTER", "Use only one audit filter.")
        state = store.read()
        if productId:
            service.product(state, productId)
        rows = [a for a in reversed(state["audit"]) if (not productId or a["productId"] == productId)
                and (not recommendationId or a["recommendationId"] == recommendationId)]
        if before:
            indexes = [i for i, a in enumerate(rows) if a["eventId"] == before]
            if not indexes:
                raise AppError(400, "INVALID_CURSOR", "Audit cursor does not match this filter.")
            rows = rows[indexes[0] + 1:]
        page = rows[:limit]
        return {"items": page, "nextCursor": page[-1]["eventId"] if len(rows) > limit else None}

    return app
