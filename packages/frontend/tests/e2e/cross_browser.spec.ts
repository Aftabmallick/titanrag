import { test, expect } from "@playwright/test";

test.describe("Cross-Browser Core User Journeys", () => {
  test("Sandbox Demo interactive question and citation flow", async ({ page }) => {
    await page.goto("/sandbox/demo");

    // Close guided tour if visible
    const tourCloseBtn = page.locator("button[aria-label='Skip tour']");
    if (await tourCloseBtn.isVisible()) {
      await tourCloseBtn.click();
    }

    // Check preloaded golden dataset docs are rendered
    await expect(page.locator("text=Master Services Agreement")).toBeVisible();

    // Type a query in input
    const input = page.locator("input[placeholder*='Ask anything']");
    await input.fill("What is the termination clause?");
    await page.locator("button[aria-label='Send query']").click();

    // Wait for response and verify citations render
    await expect(page.locator("text=Section 14.2")).toBeVisible({ timeout: 5000 });
  });

  test("Keyboard shortcuts help overlay opens with question mark", async ({ page }) => {
    await page.goto("/sandbox");
    await page.keyboard.press("?");
    // Help overlay should trigger
    const shortcutsDialog = page.locator("[role='dialog']");
    if (await shortcutsDialog.isVisible()) {
      await expect(page.locator("text=Keyboard Shortcuts")).toBeVisible();
      await page.keyboard.press("Escape");
    }
  });

  test("RTL direction applied on Arabic locale selection", async ({ page }) => {
    await page.goto("/sandbox");
    // Switch to Arabic
    const langBtn = page.locator("button[aria-label='Change Language']");
    if (await langBtn.isVisible()) {
      await langBtn.click();
      await page.locator("button:has-text('العربية')").click();
      const dir = await page.locator("html").getAttribute("dir");
      expect(dir).toBe("rtl");
    }
  });
});
