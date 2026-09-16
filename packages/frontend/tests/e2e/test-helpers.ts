import { Page } from "playwright";

export async function authenticateAndPrepare(page: Page, baseUrl: string) {
  // Add init script to prevent onboarding modal
  await page.addInitScript(() => {
    localStorage.setItem("titan_onboarding_done", "true");
  });

  await page.goto(baseUrl, { waitUntil: "networkidle" });

  const demoButton = page.locator('button:has-text("Launch Admin Sandbox")');
  if (await demoButton.isVisible({ timeout: 2000 }).catch(() => false)) {
    await demoButton.click();
    await page.waitForTimeout(2000);
  }

  // Dismiss any overlay/modal if visible
  const modalBackdrop = page.locator('div.fixed.inset-0.bg-slate-950\\/75, div.fixed.inset-0.bg-slate-950\\/80');
  if (await modalBackdrop.isVisible({ timeout: 1000 }).catch(() => false)) {
    await page.keyboard.press("Escape");
    await page.waitForTimeout(500);
  }
}
