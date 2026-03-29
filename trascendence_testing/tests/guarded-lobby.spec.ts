import { test } from "@playwright/test";

import { expectGuardedOutcome, testConfig } from "./support";

test("unauthenticated user cannot access lobby @negative @guarded", async ({ page }) => {
  await page.goto(testConfig.routes.lobby);
  await expectGuardedOutcome(page);
});
