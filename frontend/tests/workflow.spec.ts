import { test, expect } from "@playwright/test";

test("full human approval workflow, rejection, blocked proposal, audit, and persistence", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByText("SIMULATION — No real advertising spend"),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Historical demand & forecast" }),
  ).toBeVisible();
  await expect(page.getByTestId("budget")).toHaveText("$1,000.00");
  await page
    .getByRole("button", { name: "Generate recommendation", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Approve", exact: false }),
  ).toBeEnabled();
  await expect(
    page.getByText("PENDING", { exact: false }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Approve", exact: false }).click();
  await expect(page.getByRole("status")).toContainText("Approved and applied");
  await expect(page.getByTestId("budget")).toHaveText("$1,150.00");
  await expect(
    page.getByText("CAMPAIGN UPDATED", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve", exact: false }),
  ).toBeDisabled();
  await page.reload();
  await expect(page.getByTestId("budget")).toHaveText("$1,150.00");
  await expect(page.getByText("EXECUTED", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Generate new recommendation" })
    .click();
  await page.getByRole("button", { name: "Reject", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("rejected");
  await expect(page.getByTestId("budget")).toHaveText("$1,150.00");
  await page.getByLabel("SELECT PRODUCT").selectOption("smart-tv");
  await expect(page.getByTestId("budget")).toHaveText("$4,500.00");
  await page
    .getByRole("button", { name: "Generate recommendation", exact: true })
    .click();
  await expect(page.getByText("BLOCKED", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve", exact: false }),
  ).toBeDisabled();
  await expect(
    page.locator(".check").filter({ hasText: "Weekly budget <= $5,000" }),
  ).toContainText("FAIL");
  await page.getByLabel("SELECT PRODUCT").selectOption("bluetooth-speaker");
  await page
    .getByRole("button", { name: "Generate recommendation", exact: true })
    .click();
  await expect(
    page.locator(".check").filter({ hasText: "Inventory sufficient" }),
  ).toContainText("FAIL");
  await expect(
    page.getByRole("button", { name: "Approve", exact: false }),
  ).toBeDisabled();
  await page.getByLabel("SELECT PRODUCT").selectOption("streaming-device");
  await page
    .getByRole("button", { name: "Generate recommendation", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Approve", exact: false }),
  ).toBeEnabled();
  await page.screenshot({
    path: "test-results/dashboard-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("button", { name: "Approve", exact: false }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/dashboard-mobile.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
