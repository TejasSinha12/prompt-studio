import { expect, test as base } from "@playwright/test";

/** Every page blocks and records requests to non-loopback hosts. */
export const test = base.extend<{ external: string[] }>({
  external: async ({ page }, use) => {
    const attempts: string[] = [];
    await page.route("**/*", (route) => {
      const host = new URL(route.request().url()).hostname;
      if (["127.0.0.1", "localhost", "[::1]", "::1"].includes(host) || route.request().url().startsWith("data:") || route.request().url().startsWith("blob:")) {
        return route.continue();
      }
      attempts.push(route.request().url());
      return route.abort();
    });
    await use(attempts);
    expect(attempts, "the UI attempted external network requests").toEqual([]);
  },
});

export { expect };
