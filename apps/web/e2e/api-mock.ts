import type { Page } from "@playwright/test";
import fixtures from "./fixtures/api.json" with { type: "json" };

const responses = fixtures as Record<string, unknown>;

/** Serve every request to the API host from the synthetic fixtures (keyed by path). */
export async function mockApi(page: Page) {
  await page.route("http://api.test/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const body = responses[path];
    if (body === undefined) {
      await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: `no fixture for ${path}` }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
}
