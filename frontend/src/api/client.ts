export interface Product {
  productId: string;
  name: string;
  demoNote: string;
}
export interface History {
  endDate: string;
  observations: { date: string; units: number }[];
}
export interface Forecast {
  horizon: { date: string; predictedUnits: number }[];
  totalUnits: number;
  requiredInventoryUnits: number;
  confidenceScore: number | null;
  demandChangePercent: number | null;
  previousWeekUnits: number;
}
export interface Campaign {
  weeklyBudgetCents: number;
  version: number;
  inventory: { availableUnits: number };
  metrics: {
    spendCents: number;
    impressions: number;
    clicks: number;
    conversions: number;
    windowStart: string;
    windowEnd: string;
  };
}
export interface Check {
  checkId: string;
  label: string;
  status: "PASS" | "FAIL" | "PENDING";
  message: string;
}
export interface Recommendation {
  recommendationId: string;
  status: string;
  version: number;
  expiresAt: string;
  proposalHash: string;
  approvalEligible: boolean;
  generationChecks?: Check[];
  executionChecks?: Check[];
  decision?: { decision: string };
  proposal?: {
    currentWeeklyBudgetCents: number;
    proposedWeeklyBudgetCents: number;
    reasoning: string;
    assumptions: string[];
  };
  error?: { message: string };
}
export interface Audit {
  eventId: string;
  eventType: string;
  occurredAt: string;
  actor: { type: string };
  details: Record<string, unknown>;
}
export interface Page<T> {
  items: T[];
  nextCursor: string | null;
}

export async function api<T>(
  path: string,
  body?: unknown,
  key?: string,
): Promise<T> {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      "Content-Type": "application/json",
      ...(key ? { "Idempotency-Key": key } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(
      data?.error?.message ||
        `Request failed (${response.status}). Refresh and retry.`,
    );
  }
  return response.json() as Promise<T>;
}

export const money = (cents: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(cents / 100);
export const number = (value: number) =>
  new Intl.NumberFormat("en-US").format(value);
