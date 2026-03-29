import { test } from "@playwright/test";

import { expectGuardedOutcome, testConfig } from "./support";

test("unauthenticated user cannot access profile @negative @guarded", async ({ page }) => {
  await page.goto(testConfig.routes.profile);
  await expectGuardedOutcome(page);
});
