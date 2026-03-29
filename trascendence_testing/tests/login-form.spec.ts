import { test } from "@playwright/test";

import { expectLoginSurface, testConfig } from "./support";

test("login route renders a usable auth form @smoke @login", async ({ page }) => {
  await page.goto(testConfig.routes.login);
  await expectLoginSurface(page);
});
