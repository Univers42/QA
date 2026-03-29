import { expect, test } from "@playwright/test";

import { hasStorageState, testConfig } from "./support";

if (hasStorageState()) {
  test.use({ storageState: testConfig.storageStatePath });
}

test("profile loads for an authenticated session @smoke @critical", async ({ page }) => {
  test.skip(!hasStorageState(), "Set TT_STORAGE_STATE_PATH to enable authenticated profile, lobby, and chat smoke checks.");

  await page.goto(testConfig.routes.profile);
  await expect(page).not.toHaveURL(/\/(auth|login)(\/|$)/i);
  await expect(page.locator("main, [role='main'], body").first()).toBeVisible();
});
