import { test } from "@playwright/test";

import { expectGuardedOutcome, testConfig } from "./support";

test("unauthenticated user cannot access chat @negative @guarded", async ({ page }) => {
  await page.goto(testConfig.routes.chat);
  await expectGuardedOutcome(page);
});
