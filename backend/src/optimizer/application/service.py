from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from uuid import uuid4

from optimizer.domain.forecast import forecast
from optimizer.domain.guardrails import POLICY_VERSION, eligible, validate
from optimizer.domain.schemas import Proposal
from optimizer.ports.reasoner import ReasoningService
from optimizer.application.mock_campaign import apply_approved_budget


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def digest(value: dict) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                                allow_nan=False).encode()).hexdigest()


def audit(state: dict, event: str, pid: str, rid: str | None, details: dict, now: str,
          human: bool = False) -> None:
    state["audit"].append({"eventId": str(uuid4()), "occurredAt": now, "eventType": event,
                           "productId": pid, "recommendationId": rid,
                           "actor": {"type": "HUMAN" if human else "SYSTEM",
                                     "id": "local-demo-user" if human else "local-service"},
                           "details": deepcopy(details), "simulation": True})


def proposal_digest(rec: dict) -> str:
    return digest({key: rec[key] for key in ("productId", "proposal", "forecast", "inputHash",
                   "campaignVersion", "inventoryVersion", "policyVersion", "expiresAt")})


class Optimizer:
    def __init__(self, store, reasoner: ReasoningService, clock=None):
        self.store, self.reasoner = store, reasoner
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def product(state: dict, pid: str) -> dict:
        for product in state["products"]:
            if product["productId"] == pid:
                return product
        raise AppError(404, "NOT_FOUND", "Product not found.")

    def effective(self, rec: dict) -> dict:
        result = deepcopy(rec)
        if not result.get("decision") and result["status"] in ("AWAITING_APPROVAL", "BLOCKED"):
            if self.clock() >= datetime.fromisoformat(result["expiresAt"]):
                result["status"], result["approvalEligible"] = "EXPIRED", False
        return result

    def get_recommendation(self, rid: str) -> dict:
        rec = self.store.read()["recommendations"].get(rid)
        if rec is None:
            raise AppError(404, "NOT_FOUND", "Recommendation not found.")
        return self.effective(rec)

    @staticmethod
    def replay(state: dict, operation: str, body: dict):
        saved = state["idempotency"].get(operation)
        if saved:
            if saved["requestHash"] != digest(body):
                raise AppError(409, "IDEMPOTENCY_CONFLICT", "This request key was already used with a different body.")
            return deepcopy(saved["response"])
        return None

    def generate(self, pid: str, key: str) -> dict:
        # Fixture reasoning is instant and pure. The file lock covers the entire local transaction.
        # A future network reasoner needs a different orchestration adapter, not a network call under this lock.
        with self.store.transaction() as state:
            product = self.product(state, pid)
            operation = f"local-demo-user:generate:{pid}:{key}"
            if (saved := self.replay(state, operation, {})) is not None:
                return saved
            now = self.clock()
            timestamp, rid = now.isoformat(), str(uuid4())
            campaign, history = deepcopy(state["campaigns"][pid]), deepcopy(state["histories"][pid])
            audit(state, "RECOMMENDATION_REQUESTED", pid, rid, {}, timestamp, human=True)
            try:
                prediction = forecast(history)
                context = {"product": deepcopy(product), "history": history,
                           "forecast": prediction, "campaign": campaign}
                proposal = Proposal.model_validate(self.reasoner.recommend(deepcopy(context))).model_dump()
                proposal["currentWeeklyBudgetCents"] = campaign["weeklyBudgetCents"]
                checks = validate(campaign, prediction, proposal["proposedWeeklyBudgetCents"],
                                  fresh=history["endDate"] == (now.date() - timedelta(days=1)).isoformat())
                for check in checks:
                    check["checkedAt"] = timestamp
                expires = min(now + timedelta(minutes=30),
                              (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0))
                rec = {"recommendationId": rid, "productId": pid,
                       "status": "AWAITING_APPROVAL" if eligible(checks) else "BLOCKED", "version": 1,
                       "createdAt": timestamp, "expiresAt": expires.isoformat(), "simulation": True,
                       "proposal": proposal, "forecast": prediction, "generationChecks": checks,
                       "executionChecks": [], "approvalEligible": eligible(checks),
                       "campaignVersion": campaign["version"], "inventoryVersion": campaign["inventory"]["version"],
                       "policyVersion": POLICY_VERSION, "reasoner": "FixtureReasoner",
                       "inputSnapshot": context, "inputHash": digest(context)}
                rec["proposalHash"] = proposal_digest(rec)
                audit(state, "RECOMMENDATION_GENERATED", pid, rid, {"proposal": proposal, "proposalHash": rec["proposalHash"]}, timestamp)
                audit(state, "VALIDATION_COMPLETED", pid, rid, {"checks": checks}, timestamp)
            except (ValueError, KeyError, TypeError) as error:
                rec = {"recommendationId": rid, "productId": pid, "status": "FAILED", "version": 1,
                       "createdAt": timestamp, "expiresAt": timestamp, "simulation": True,
                       "approvalEligible": False, "error": {"code": "INVALID_REASONING_OR_INPUT",
                       "message": "Generation failed input or proposal validation."}}
                audit(state, "RECOMMENDATION_FAILED", pid, rid, {"errorType": type(error).__name__}, timestamp)
            state["recommendations"][rid] = rec
            state["idempotency"][operation] = {"requestHash": digest({}), "response": deepcopy(rec)}
            return deepcopy(rec)

    def decide(self, rid: str, body: dict, key: str) -> dict:
        with self.store.transaction() as state:
            operation = f"local-demo-user:decision:{rid}:{key}"
            if (saved := self.replay(state, operation, body)) is not None:
                return saved
            rec = state["recommendations"].get(rid)
            if rec is None:
                raise AppError(404, "NOT_FOUND", "Recommendation not found.")
            if rec.get("decision") or rec["status"] not in ("AWAITING_APPROVAL", "BLOCKED"):
                raise AppError(409, "DECISION_CONFLICT", "This recommendation is already final.")
            if (body["expectedVersion"] != rec["version"] or body["proposalHash"] != rec["proposalHash"]
                    or proposal_digest(rec) != rec["proposalHash"]):
                raise AppError(409, "PROPOSAL_CONFLICT", "The reviewed proposal has changed. Refresh before deciding.")
            now, pid = self.clock(), rec["productId"]
            timestamp = now.isoformat()
            expired = now >= datetime.fromisoformat(rec["expiresAt"])
            checks, action = [], None
            if expired:
                outcome = "EXPIRED"
            elif body["decision"] == "REJECT":
                outcome = "REJECTED"
            else:
                campaign, history = state["campaigns"][pid], state["histories"][pid]
                prediction = forecast(history)
                same = (campaign["version"] == rec["campaignVersion"]
                        and campaign["inventory"]["version"] == rec["inventoryVersion"])
                fresh = (same and history == rec["inputSnapshot"]["history"]
                         and history["endDate"] == (now.date() - timedelta(days=1)).isoformat()
                         and prediction == rec["forecast"] and rec["policyVersion"] == POLICY_VERSION)
                checks = validate(campaign, prediction, rec["proposal"]["proposedWeeklyBudgetCents"],
                                  approved=True, fresh=fresh, phase="EXECUTION")
                for check in checks:
                    check["checkedAt"] = timestamp
                outcome = "STALE" if not same else "EXECUTED" if eligible(checks) and rec["approvalEligible"] else "BLOCKED"
            decision = {"decisionId": str(uuid4()), "decision": body["decision"], "actorId": "local-demo-user",
                        "decidedAt": timestamp, "proposalHash": rec["proposalHash"], "outcome": outcome,
                        "comment": body.get("comment", "")}
            if outcome == "EXECUTED":
                action = apply_approved_budget(state, rec, decision, checks, timestamp)
            rec.update(status=outcome, version=rec["version"] + 1, approvalEligible=False,
                       decision=decision, executionChecks=checks)
            if action:
                rec["action"] = action
            state["decisions"][rid] = decision
            audit(state, "DECISION_RECORDED", pid, rid, decision, timestamp, human=True)
            if checks:
                audit(state, "EXECUTION_VALIDATED", pid, rid, {"checks": checks}, timestamp)
            if action:
                audit(state, "CAMPAIGN_UPDATED", pid, rid, action, timestamp)
            elif outcome in ("BLOCKED", "STALE", "EXPIRED"):
                audit(state, "RECOMMENDATION_EXPIRED" if expired else "EXECUTION_BLOCKED", pid, rid,
                      {"outcome": outcome}, timestamp)
            result = {"recommendationId": rid, "status": outcome, "decision": decision,
                      "executionChecks": checks, "simulation": True}
            if action:
                result["action"] = action
            state["idempotency"][operation] = {"requestHash": digest(body), "response": deepcopy(result)}
            return result
