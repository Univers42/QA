import { test } from "@playwright/test";

import { expectGracefulDegradation, submitLogin, testConfig } from "./support";

test("auth degradation surfaces a graceful error when the auth backend fails @negative @degraded", async ({
  page
}) => {
  await page.route(testConfig.authApiPattern, async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ error: "service_unavailable", message: "Auth backend unavailable" })
    });
  });

  await page.goto(testConfig.routes.login);
  await submitLogin(
    page,
    testConfig.credentials.email || "qa@example.com",
    testConfig.credentials.password || "invalid-password"
  );
  await expectGracefulDegradation(page);
});
