import type { Forecast, History } from "../api/client";

export function DemandChart({
  history,
  forecast,
}: {
  history: History;
  forecast: Forecast;
}) {
  const actual = history.observations.map((row) => ({
    date: row.date,
    value: row.units,
  }));
  const predicted = forecast.horizon.map((row) => ({
    date: row.date,
    value: row.predictedUnits,
  }));
  const all = [...actual, ...predicted];
  const max = Math.ceil(Math.max(...all.map((r) => r.value)) / 20) * 20 || 20;
  const x = (i: number) => 44 + (i / (all.length - 1)) * 710;
  const y = (v: number) => 215 - (v / max) * 180;
  const path = (rows: typeof actual, offset: number) =>
    rows
      .map((r, i) => `${i ? "L" : "M"}${x(i + offset)},${y(r.value)}`)
      .join(" ");
  return (
    <>
      <svg
        viewBox="0 0 780 255"
        role="img"
        aria-label="90 days of synthetic demand followed by a seven-day forecast"
        className="chart"
      >
        <defs>
          <linearGradient id="demandFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#208471" stopOpacity=".18" />
            <stop offset="100%" stopColor="#208471" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 0.25, 0.5, 0.75, 1].map((f) => (
          <g key={f}>
            <line
              x1="44"
              x2="754"
              y1={y(max * f)}
              y2={y(max * f)}
              stroke="#e6ece8"
            />
            <text x="32" y={y(max * f) + 4} textAnchor="end">
              {max * f}
            </text>
          </g>
        ))}
        <rect
          x={x(89)}
          y="20"
          width={x(96) - x(89)}
          height="195"
          fill="#e9f2ef"
        />
        <path
          d={`${path(actual, 0)} L${x(89)},215 L44,215 Z`}
          fill="url(#demandFill)"
        />
        <path
          d={path(actual, 0)}
          fill="none"
          stroke="#287d6c"
          strokeWidth="2.5"
        />
        <path
          d={path([actual[89], ...predicted], 89)}
          fill="none"
          stroke="#b47c30"
          strokeWidth="2.5"
          strokeDasharray="5 4"
        />
        {[0, 30, 60, 89].map((i) => (
          <text key={i} x={x(i)} y="240" textAnchor="middle">
            {actual[i].date.slice(5)}
          </text>
        ))}
        <text x="48" y="17">
          UNITS / DAY
        </text>
      </svg>
      <div className="legend">
        <span>
          <i className="dot green" /> Historical demand
        </span>
        <span>
          <i className="dot gold" /> 7-day forecast
        </span>
        <span>90 days · synthetic data</span>
      </div>
      <details className="data-table">
        <summary>View accessible demand data</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Units</th>
                <th>Type</th>
              </tr>
            </thead>
            <tbody>
              {all.map((r, i) => (
                <tr key={r.date}>
                  <td>{r.date}</td>
                  <td>{r.value}</td>
                  <td>{i < 90 ? "Historical" : "Forecast"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
