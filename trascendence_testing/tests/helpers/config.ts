/**
 * Centralizes environment-driven configuration for the Transcendence testing
 * module, including routes, credentials, and storage state.
 */
import fs from "node:fs";

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

export const guardedScreens: Array<{ name: string; path: string }> = [
  { name: "profile", path: testConfig.routes.profile },
  { name: "lobby", path: testConfig.routes.lobby },
  { name: "chat", path: testConfig.routes.chat }
];

export function hasCredentialLogin(): boolean {
  return Boolean(testConfig.credentials.email && testConfig.credentials.password);
}

export function hasStorageState(): boolean {
  return Boolean(testConfig.storageStatePath) && fs.existsSync(testConfig.storageStatePath);
}
