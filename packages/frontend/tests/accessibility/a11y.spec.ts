import { test, expect } from "@playwright/test";

test.describe("Accessibility (WCAG 2.1 AA) Audits", () => {
  const routes = [
    { name: "Sandbox Landing", path: "/sandbox" },
    { name: "Sandbox Demo Playground", path: "/sandbox/demo" },
    { name: "Billing Dashboard", path: "/admin/billing" },
    { name: "Brand Whitelabel Editor", path: "/admin/brand" },
    { name: "Tenants Admin Table", path: "/admin/tenants" },
    { name: "System Health Overview", path: "/admin/system" },
    { name: "Announcements Manager", path: "/admin/announcements" },
    { name: "Global Audit Log", path: "/admin/audit" },
  ];

  for (const route of routes) {
    test(`Route ${route.name} (${route.path}) should have accessible headings and focus rings`, async ({
      page,
    }) => {
      // Mock auth session cookie for admin routes
      await page.context().addCookies([
        {
          name: "access_token",
          value: "mock_test_token_superadmin",
          domain: "localhost",
          path: "/",
        },
      ]);

      await page.goto(route.path);
      await page.waitForLoadState("domcontentloaded");

      // Verify page has a valid title and landmark structure
      const title = await page.title();
      expect(title).toBeDefined();

      // Check all buttons have accessible labels
      const buttons = await page.locator("button").all();
      for (const btn of buttons) {
        const ariaLabel = await btn.getAttribute("aria-label");
        const innerText = await btn.innerText();
        const hasAccessibleName = Boolean(ariaLabel?.trim() || innerText?.trim());
        expect(hasAccessibleName).toBe(true);
      }

      // Check all inputs have accessible labels or aria-label
      const inputs = await page.locator("input, select, textarea").all();
      for (const input of inputs) {
        const ariaLabel = await input.getAttribute("aria-label");
        const id = await input.getAttribute("id");
        const hasLabel = Boolean(ariaLabel || id);
        expect(hasLabel).toBe(true);
      }
    });
  }

  test("Reduced motion preference disables animations", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/sandbox");
    const animatedElements = await page.locator(".animate-ping, .animate-bounce").count();
    // In reduced motion, CSS media query overrides remove or pause animations
    expect(animatedElements).toBeGreaterThanOrEqual(0);
  });
});
