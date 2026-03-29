import { test } from "@playwright/test";

import { expectGenericErrorScreen, testConfig } from "./support";

test("non-existent routes show a visible error state @smoke @errors", async ({ page }) => {
  await page.goto(testConfig.routes.notFound);
  await expectGenericErrorScreen(page);
});
