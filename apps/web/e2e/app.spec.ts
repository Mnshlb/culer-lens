import { expect, test } from "@playwright/test";
import { mockApi } from "./api-mock";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("overview shows the next match and a probability for each outcome", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "What's happening with Barcelona" })).toBeVisible();
  await expect(page.getByText("chance of a Barça win")).toBeVisible();
  await expect(page.getByText("Real Madrid").first()).toBeVisible();
  await page.getByRole("button", { name: "Reveal result" }).click();
  await expect(page.getByText("0-4")).toBeVisible();
});

test("every page says it is a personal project, not affiliated with the club or StatsBomb", async ({ page }) => {
  for (const path of ["/", "/about"]) {
    await page.goto(path);
    await expect(page.getByText(/Not affiliated with, endorsed by or\s+connected to FC Barcelona or StatsBomb/)).toBeVisible();
  }
  await expect(page.getByRole("heading", { name: "About this project" })).toBeVisible();
});

test("match centre: predicted XI opens a player panel with reasons", async ({ page }) => {
  await page.goto("/matches/1");
  await expect(page.getByText("Team comparison")).toBeVisible();
  await page.getByRole("button", { name: /Ten, start probability/ }).click();
  await expect(page.getByText("Why selected?")).toBeVisible();
  await expect(page.getByText("Started 5 of the last 5")).toBeVisible();
});

test("match centre hides the analysis until the result is revealed", async ({ page }) => {
  await page.goto("/matches/1");
  await expect(page.getByText(/hidden until the result is revealed/)).toBeVisible();
  await page.getByRole("button", { name: "Reveal result" }).first().click();
  await expect(page.getByRole("tab", { name: "Shot map" })).toBeVisible();
});

test("player page renders the heatmap and zone details", async ({ page }) => {
  await page.goto("/players/10");
  await expect(page.getByRole("heading", { name: "Ten" })).toBeVisible();
  await expect(page.getByText("Spatial profile").first()).toBeVisible();
  await page.getByRole("img", { name: "Football pitch" }).first().locator("rect[aria-label]").first().click();
  await expect(page.getByText("Actions", { exact: true })).toBeVisible();
});

test("model intelligence shows benchmarks and explanations", async ({ page }) => {
  await page.goto("/model");
  await expect(page.getByText("Against the benchmarks")).toBeVisible();
  await expect(page.getByText("Market (average odds)")).toBeVisible();
  await expect(page.getByText("Grouped permutation importance, holdout")).toBeVisible();
});

test("methodology lists the limitations", async ({ page }) => {
  await page.goto("/about");
  await expect(page.getByText("Event data is not tracking data")).toBeVisible();
  await expect(page.getByText("The workload index is not medical fatigue")).toBeVisible();
});

test("unknown API resources show a clear message", async ({ page }) => {
  await page.goto("/matches/999");
  await expect(page.getByText("Not available")).toBeVisible();
});
