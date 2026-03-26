/**
 * Covers the current smoke slice for the frontend: login, guarded routes,
 * error screens, and auth degradation behaviour.
 */
import { expect, test } from "@playwright/test";

import { guardedScreens, hasCredentialLogin, hasStorageState, testConfig } from "../helpers/config";
import {
  expectGenericErrorScreen,
  expectGracefulDegradation,
  expectGuardedOutcome,
  expectLoginSurface,
  submitLogin
} from "../helpers/ui";

test("login route renders a usable auth form @smoke @login", async ({ page }) => {
  await page.goto(testConfig.routes.login);
  await expectLoginSurface(page);
});

test("login flow accepts valid credentials when configured @smoke @login @auth", async ({ page, context }) => {
  test.skip(
    !hasCredentialLogin(),
    "Set TT_E2E_EMAIL and TT_E2E_PASSWORD to enable credential-based login smoke."
  );

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

for (const screen of guardedScreens) {
  test(`unauthenticated user cannot access ${screen.name} @negative @guarded`, async ({ page }) => {
    await page.goto(screen.path);
    await expectGuardedOutcome(page);
  });
}

if (hasStorageState()) {
  test.describe("authenticated critical screens @smoke @critical", () => {
    test.use({ storageState: testConfig.storageStatePath });

    for (const screen of guardedScreens) {
      test(`${screen.name} loads for an authenticated session @smoke @critical`, async ({ page }) => {
        await page.goto(screen.path);
        await expect(page).not.toHaveURL(/\/(auth|login)(\/|$)/i);
        await expect(page.locator("main, [role='main'], body").first()).toBeVisible();
      });
    }
  });
} else {
  test("authenticated critical screens require TT_STORAGE_STATE_PATH @smoke @critical", async () => {
    test.skip(true, "Set TT_STORAGE_STATE_PATH to enable authenticated profile, lobby, and chat smoke checks.");
  });
}

test("non-existent routes show a visible error state @smoke @errors", async ({ page }) => {
  await page.goto(testConfig.routes.notFound);
  await expectGenericErrorScreen(page);
});

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
