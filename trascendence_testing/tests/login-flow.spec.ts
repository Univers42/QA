import { expect, test } from "@playwright/test";

import { hasCredentialLogin, submitLogin, testConfig } from "./support";

test("login flow accepts valid credentials when configured @smoke @login @auth", async ({ page, context }) => {
  test.skip(!hasCredentialLogin(), "Set TT_E2E_EMAIL and TT_E2E_PASSWORD to enable credential-based login smoke.");

  await page.goto(testConfig.routes.login);
  await submitLogin(page, testConfig.credentials.email, testConfig.credentials.password);

  await expect
    .poll(async () => {
      const currentUrl = page.url();
      if (!/\/(auth|login)(\/|$)/i.test(currentUrl)) {
        return "redirected";
      }

      const cookies = await context.cookies();
      if (cookies.length > 0) {
        return "cookie";
      }

      return "";
    })
    .not.toBe("");
});
