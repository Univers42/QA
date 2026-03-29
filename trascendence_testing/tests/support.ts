import fs from "node:fs";

import { expect, type Locator, type Page } from "@playwright/test";

type RouteConfig = {
  login: string;
  profile: string;
  lobby: string;
  chat: string;
  notFound: string;
};

function envValue(name: string, fallback = ""): string {
  const value = process.env[name];
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

export const testConfig = {
  baseURL:
    envValue("TT_BASE_URL") ||
    envValue("PLAYWRIGHT_BASE_URL") ||
    envValue("FRONTEND_URL") ||
    "http://127.0.0.1:5173",
  routes: {
    login: envValue("TT_LOGIN_PATH", "/auth"),
    profile: envValue("TT_PROFILE_PATH", "/profile"),
    lobby: envValue("TT_LOBBY_PATH", "/lobby"),
    chat: envValue("TT_CHAT_PATH", "/chat"),
    notFound: envValue("TT_NOT_FOUND_PATH", "/__qa_missing_route__")
  } satisfies RouteConfig,
  authApiPattern: envValue("TT_AUTH_API_PATTERN", "**/auth/**"),
  credentials: {
    email: envValue("TT_E2E_EMAIL"),
    password: envValue("TT_E2E_PASSWORD")
  },
  storageStatePath: envValue("TT_STORAGE_STATE_PATH")
};

const guardedPatterns = [
  /unauthorized/i,
  /forbidden/i,
  /access denied/i,
  /sign in/i,
  /log in/i,
  /iniciar sesi[oó]n/i,
  /inicia sesi[oó]n/i
];

const errorPatterns = [/\b404\b/i, /not found/i, /page not found/i, /no existe/i, /error/i];

const degradationPatterns = [
  /service unavailable/i,
  /temporarily unavailable/i,
  /try again/i,
  /please try again/i,
  /error/i,
  /no ha sido posible/i,
  /int[eé]ntalo de nuevo/i
];

export function hasCredentialLogin(): boolean {
  return Boolean(testConfig.credentials.email && testConfig.credentials.password);
}

export function hasStorageState(): boolean {
  return Boolean(testConfig.storageStatePath) && fs.existsSync(testConfig.storageStatePath);
}

async function firstVisible(page: Page, selectors: string[], label: string): Promise<Locator> {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    if ((await locator.count()) > 0) {
      await expect(locator, `Expected ${label} via selector ${selector}`).toBeVisible();
      return locator;
    }
  }

  throw new Error(`Could not locate ${label}. Checked selectors: ${selectors.join(", ")}`);
}

export async function loginFields(page: Page): Promise<{
  email: Locator;
  password: Locator;
  submit: Locator;
}> {
  const email = await firstVisible(
    page,
    ['input[type="email"]', 'input[name="email"]', '[data-testid="login-email"]', '[autocomplete="email"]'],
    "email field"
  );

  const password = await firstVisible(
    page,
    [
      'input[type="password"]',
      'input[name="password"]',
      '[data-testid="login-password"]',
      '[autocomplete="current-password"]'
    ],
    "password field"
  );

  const namedButton = page
    .getByRole("button", {
      name: /log in|login|sign in|iniciar sesi[oó]n|acceder/i
    })
    .first();

  const submit =
    (await namedButton.count()) > 0
      ? namedButton
      : await firstVisible(
          page,
          ['form button[type="submit"]', 'button[type="submit"]', '[data-testid="login-submit"]'],
          "submit button"
        );

  await expect(submit).toBeVisible();
  return { email, password, submit };
}

export async function expectLoginSurface(page: Page): Promise<void> {
  await expect(page.locator("body")).toBeVisible();
  await loginFields(page);
}

export async function submitLogin(page: Page, email: string, password: string): Promise<void> {
  const fields = await loginFields(page);
  await fields.email.fill(email);
  await fields.password.fill(password);
  await fields.submit.click();
}

export async function expectGuardedOutcome(page: Page): Promise<void> {
  await expect
    .poll(async () => {
      const currentUrl = page.url();
      if (/\/(auth|login)(\/|$)/i.test(currentUrl)) {
        return "redirect";
      }

      const text = await page.locator("body").innerText();
      if (guardedPatterns.some((pattern) => pattern.test(text))) {
        return "guarded-copy";
      }

      return "";
    })
    .not.toBe("");
}

export async function expectGenericErrorScreen(page: Page): Promise<void> {
  await expect
    .poll(async () => {
      const text = await page.locator("body").innerText();
      return errorPatterns.some((pattern) => pattern.test(text));
    })
    .toBeTruthy();
}

export async function expectGracefulDegradation(page: Page): Promise<void> {
  await expect
    .poll(async () => {
      const text = await page.locator("body").innerText();
      return degradationPatterns.some((pattern) => pattern.test(text));
    })
    .toBeTruthy();
}
