import React, { useEffect, useRef, useState } from "react";
import {
  api,
  money,
  number,
  type Product,
  type History,
  type Forecast,
  type Campaign,
  type Recommendation,
  type Audit,
  type Page,
} from "../api/client";
import { DemandChart } from "../components/DemandChart";

export default function App() {
  const [products, setProducts] = useState<Product[]>([]);
  const [productId, setProductId] = useState("wireless-headphones");
  const [data, setData] = useState<{
    history: History;
    forecast: Forecast;
    campaign: Campaign;
  } | null>(null);
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [events, setEvents] = useState<Audit[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tick, setTick] = useState(Date.now());
  const [reload, setReload] = useState(0);
  const pending = useRef<{
    operation: string;
    key: string;
    body: unknown;
  } | null>(null);
  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setData(null);
    setRec(null);
    setEvents([]);
    setError("");
    setNotice("");
    pending.current = null;
    const base = `/v1/products/${productId}`;
    Promise.all([
      api<History>(`${base}/history`),
      api<Forecast>(`${base}/forecast`),
      api<Campaign>(`${base}/campaign`),
      api<Page<Recommendation>>(`${base}/recommendations`),
      api<Page<Audit>>(`/v1/audit?productId=${productId}`),
      api<{ items: Product[] }>("/v1/products"),
    ])
      .then(
        ([history, forecast, campaign, recommendations, audit, catalog]) => {
          if (!ignore) {
            setProducts(catalog.items);
            setData({ history, forecast, campaign });
            setRec(recommendations.items[0] ?? null);
            setEvents(audit.items);
            setCursor(audit.nextCursor);
          }
        },
      )
      .catch((e) => {
        if (!ignore) setError(e.message);
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [productId, reload]);
  useEffect(() => {
    const timer = window.setInterval(() => setTick(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  async function refresh() {
    const [campaign, audit] = await Promise.all([
      api<Campaign>(`/v1/products/${productId}/campaign`),
      api<Page<Audit>>(`/v1/audit?productId=${productId}`),
    ]);
    setData((current) => (current ? { ...current, campaign } : current));
    setEvents(audit.items);
    setCursor(audit.nextCursor);
  }
  function requestKey(operation: string, body: unknown) {
    if (!pending.current || pending.current.operation !== operation)
      pending.current = { operation, key: crypto.randomUUID(), body };
    return pending.current;
  }
  async function generate() {
    setBusy(true);
    setError("");
    setNotice("");
    const request = requestKey(`generate:${productId}`, {});
    try {
      const result = await api<Recommendation>(
        `/v1/products/${productId}/recommendations`,
        request.body,
        request.key,
      );
      setRec(result);
      pending.current = null;
      setNotice(
        result.status === "BLOCKED"
          ? "Recommendation blocked. Review the failed guardrails below."
          : result.status === "FAILED"
            ? "Generation failed validation."
            : "Recommendation ready. Review every check before making your decision.",
      );
      await refresh();
    } catch (e) {
      setError((e as Error).message + " Retry uses the same request key.");
    } finally {
      setBusy(false);
    }
  }
  async function decide(decision: "APPROVE" | "REJECT") {
    if (!rec) return;
    setBusy(true);
    setError("");
    setNotice("");
    const body = {
      decision,
      expectedVersion: rec.version,
      proposalHash: rec.proposalHash,
    };
    const request = requestKey(
      `decision:${rec.recommendationId}:${decision}`,
      body,
    );
    try {
      const result = await api<{ status: string }>(
        `/v1/recommendations/${rec.recommendationId}/decision`,
        request.body,
        request.key,
      );
      pending.current = null;
      setNotice(
        result.status === "EXECUTED"
          ? "Approved and applied to the mock campaign. No real money was spent."
          : result.status === "REJECTED"
            ? "Recommendation rejected. Campaign budget is unchanged."
            : `${result.status}: no campaign change was made. Generate a new recommendation to continue.`,
      );
      setRec(
        await api<Recommendation>(
          `/v1/recommendations/${rec.recommendationId}`,
        ),
      );
      await refresh();
    } catch (e) {
      setError(
        (e as Error).message +
          " Retry the same decision to recover its result.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function moreAudit() {
    if (!cursor) return;
    setBusy(true);
    try {
      const page = await api<Page<Audit>>(
        `/v1/audit?productId=${productId}&before=${cursor}`,
      );
      setEvents((current) => [...current, ...page.items]);
      setCursor(page.nextCursor);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const product = products.find((p) => p.productId === productId);
  const expired = !!rec && !rec.decision && tick >= Date.parse(rec.expiresAt);
  const checks = rec?.executionChecks?.length
    ? rec.executionChecks
    : (rec?.generationChecks ?? []);
  const ready =
    rec?.status === "AWAITING_APPROVAL" &&
    rec.approvalEligible &&
    !expired &&
    !rec.decision;
  const rejectable =
    !!rec &&
    ["AWAITING_APPROVAL", "BLOCKED"].includes(rec.status) &&
    !expired &&
    !rec.decision;
  const change = data?.forecast.demandChangePercent;
  return (
    <>
      <div className="simulation">
        <span className="simulation-icon">◈</span> SIMULATION — No real
        advertising spend <span className="local-tag">LOCAL PROTOTYPE</span>
      </div>
      <header className="topbar">
        <a className="brand" href="/">
          <span className="brand-mark">
            J<span>↗</span>
          </span>
          <span>
            JMB Advertising<small>DEMAND & CAMPAIGN OPTIMIZER</small>
          </span>
        </a>
        <div className="header-right">
          <span className="status-dot" /> FixtureReasoner{" "}
          <span className="avatar" title="Local demo identity">
            LD
          </span>
        </div>
      </header>
      <main>
        <div className="page-heading">
          <div>
            <p className="eyebrow">CAMPAIGN INTELLIGENCE / DASHBOARD</p>
            <h1>
              Demand-led decisions.
              <br />
              <span>Human-led control.</span>
            </h1>
            <p className="subtitle">
              Forecast demand. Review the reasoning. You decide what happens
              next.
            </p>
          </div>
          <div className="product-control">
            <label htmlFor="product">SELECT PRODUCT</label>
            <select
              id="product"
              value={productId}
              disabled={busy}
              onChange={(e) => setProductId(e.target.value)}
            >
              {products.map((p) => (
                <option key={p.productId} value={p.productId}>
                  {p.name}
                </option>
              ))}
            </select>
            <span>{product?.demoNote || "Loading products…"}</span>
          </div>
        </div>
        {error && (
          <div className="message error" role="alert">
            {error}{" "}
            <button onClick={() => setReload((r) => r + 1)} disabled={busy}>
              Refresh dashboard
            </button>
          </div>
        )}
        {notice && (
          <div className="message success" role="status">
            {notice}
          </div>
        )}
        {loading && (
          <div className="panel loading" role="status">
            Loading your simulation…
          </div>
        )}
        {data && (
          <>
            <section className="stats" aria-label="Campaign summary">
              <article>
                <span className="stat-label">7-DAY DEMAND FORECAST</span>
                <div className="stat-value">
                  {change == null
                    ? "N/A"
                    : `${change >= 0 ? "+" : ""}${change.toFixed(1)}%`}
                  <span className="mini-trend">↗</span>
                </div>
                <p>
                  {number(data.forecast.totalUnits)} units · vs. previous 7 days
                </p>
              </article>
              <article>
                <span className="stat-label">FORECAST CONFIDENCE</span>
                <div className="stat-value">
                  {data.forecast.confidenceScore == null
                    ? "N/A"
                    : `${(data.forecast.confidenceScore * 100).toFixed(1)}%`}
                </div>
                <p>Backtest accuracy · minimum 80%</p>
              </article>
              <article>
                <span className="stat-label">CURRENT WEEKLY BUDGET</span>
                <div className="stat-value" data-testid="budget">
                  {money(data.campaign.weeklyBudgetCents)}
                </div>
                <p>Simulated · $5,000 campaign cap</p>
              </article>
              <article>
                <span className="stat-label">AVAILABLE INVENTORY</span>
                <div className="stat-value">
                  {number(data.campaign.inventory.availableUnits)}
                  <small>units</small>
                </div>
                <p>
                  {number(data.forecast.requiredInventoryUnits)} required with
                  10% buffer
                </p>
              </article>
            </section>
            <div className="workspace">
              <div className="left-column">
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <p className="eyebrow">01 / UNDERSTAND DEMAND</p>
                      <h2>Historical demand & forecast</h2>
                    </div>
                    <span className="pill">90D + 7D</span>
                  </div>
                  <DemandChart
                    history={data.history}
                    forecast={data.forecast}
                  />
                  <div className="forecast-days">
                    {data.forecast.horizon.map((day) => (
                      <div key={day.date}>
                        <span>
                          {new Date(day.date + "T12:00:00Z").toLocaleDateString(
                            "en-US",
                            { weekday: "short", timeZone: "UTC" },
                          )}
                        </span>
                        <strong>{day.predictedUnits}</strong>
                        <small>{day.date.slice(5)}</small>
                      </div>
                    ))}
                  </div>
                  <p className="method-note">
                    Each forecast uses the last four matching weekdays.
                    Confidence = 1 − WAPE across four 7-day backtests; it is an
                    accuracy score, not a probability.
                  </p>
                </section>
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <p className="eyebrow">SIMULATED PERFORMANCE</p>
                      <h2>Current campaign</h2>
                    </div>
                    <span className="pill">LAST 7 DAYS</span>
                  </div>
                  <div className="campaign-metrics">
                    <div>
                      <span>Spend</span>
                      <strong>{money(data.campaign.metrics.spendCents)}</strong>
                    </div>
                    <div>
                      <span>Impressions</span>
                      <strong>
                        {number(data.campaign.metrics.impressions)}
                      </strong>
                    </div>
                    <div>
                      <span>Clicks</span>
                      <strong>{number(data.campaign.metrics.clicks)}</strong>
                    </div>
                    <div>
                      <span>Conversions</span>
                      <strong>
                        {number(data.campaign.metrics.conversions)}
                      </strong>
                    </div>
                  </div>
                  <p className="method-note">
                    Synthetic performance · {data.campaign.metrics.windowStart}{" "}
                    to {data.campaign.metrics.windowEnd}. Budget changes do not
                    fabricate new performance.
                  </p>
                </section>
              </div>
              <section className="panel recommendation">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">02 / REVIEW & DECIDE</p>
                    <h2>AI recommendation</h2>
                  </div>
                  <span className="spark">✧</span>
                </div>
                <p className="reasoner-note">
                  FixtureReasoner · deterministic demo · no LLM calls
                </p>
                {!rec && (
                  <div className="empty-state">
                    <div>↗</div>
                    <h3>A proposal, never an automatic action.</h3>
                    <p>
                      Generate a recommendation from demand, campaign
                      performance, and available inventory.
                    </p>
                  </div>
                )}
                {rec?.proposal && (
                  <>
                    <div className="recommendation-title">
                      <span className="pill">
                        {expired ? "EXPIRED" : rec.status.replaceAll("_", " ")}
                      </span>
                      <h3>
                        {rec.proposal.proposedWeeklyBudgetCents >
                        rec.proposal.currentWeeklyBudgetCents
                          ? "Increase"
                          : "Maintain"}{" "}
                        weekly budget
                      </h3>
                      <div className="budget-change">
                        <span>
                          {money(rec.proposal.currentWeeklyBudgetCents)}
                        </span>
                        <i>→</i>
                        <strong>
                          {money(rec.proposal.proposedWeeklyBudgetCents)}
                        </strong>
                      </div>
                    </div>
                    <div className="reason">
                      <h4>Agent reasoning</h4>
                      <p>{rec.proposal.reasoning}</p>
                    </div>
                    <div className="checks">
                      <h4>
                        DETERMINISTIC GUARDRAILS{" "}
                        <span>
                          {rec.executionChecks?.length
                            ? "REVALIDATED"
                            : "PRE-APPROVAL"}
                        </span>
                      </h4>
                      {checks.map((c) => (
                        <div
                          className="check"
                          key={c.checkId}
                          title={c.message}
                        >
                          <span
                            className={`check-status ${c.status.toLowerCase()}`}
                          >
                            {c.status === "PASS"
                              ? "✓"
                              : c.status === "FAIL"
                                ? "×"
                                : "○"}{" "}
                            {c.status}
                          </span>
                          <span>{c.label}</span>
                        </div>
                      ))}
                    </div>
                    <div className="decisions">
                      <button
                        className="approve"
                        disabled={busy || !ready}
                        onClick={() => decide("APPROVE")}
                      >
                        ✓ Approve
                      </button>
                      <button
                        className="reject"
                        disabled={busy || !rejectable}
                        onClick={() => decide("REJECT")}
                      >
                        Reject
                      </button>
                    </div>
                    <p className="decision-note">
                      {expired
                        ? "Expired. Generate a fresh recommendation."
                        : rec.decision
                          ? "Decision recorded in the audit history."
                          : `Explicit approval required. Expires ${new Date(rec.expiresAt).toLocaleTimeString()}.`}
                    </p>
                  </>
                )}
                {rec?.status === "FAILED" && (
                  <p role="alert">{rec.error?.message}</p>
                )}
                <button className="generate" disabled={busy} onClick={generate}>
                  {busy
                    ? "Processing…"
                    : rec
                      ? "Generate new recommendation"
                      : "Generate recommendation"}{" "}
                  <span aria-hidden="true">↗</span>
                </button>
              </section>
            </div>
            <section className="panel audit-panel">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">03 / TRACE EVERY DECISION</p>
                  <h2>Audit history</h2>
                </div>
                <span className="pill">APPEND-ONLY</span>
              </div>
              <p className="method-note audit-note">
                Recommendations, validation results, human decisions, and mock
                actions are saved together with local state.
              </p>
              <div className="audit-table">
                <table>
                  <thead>
                    <tr>
                      <th>Event</th>
                      <th>Actor</th>
                      <th>Time</th>
                      <th>Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((event) => (
                      <tr key={event.eventId}>
                        <td>
                          <span className="event-dot" />
                          {event.eventType.replaceAll("_", " ")}
                        </td>
                        <td>
                          {event.actor.type === "HUMAN"
                            ? "Local demo user"
                            : "System"}
                        </td>
                        <td>{new Date(event.occurredAt).toLocaleString()}</td>
                        <td>
                          <details>
                            <summary>View record</summary>
                            <pre>{JSON.stringify(event.details, null, 2)}</pre>
                          </details>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {cursor && (
                <button className="more" disabled={busy} onClick={moreAudit}>
                  Load older events
                </button>
              )}
            </section>
          </>
        )}
        <footer>
          <span>LOCAL FIRST. HUMAN APPROVED.</span>
          <span>
            Deterministic forecast → Fixture reasoning → Guardrails → Your
            decision
          </span>
        </footer>
      </main>
    </>
  );
}
