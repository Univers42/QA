import { MongoClient, Db, Collection } from "mongodb";
import * as dotenv from "dotenv";

dotenv.config();

// ── Types ────────────────────────────────────────────────────────────────────

export interface TestDefinition {
  _id?: unknown;
  id: string;               // e.g. "AUTH-001"
  title: string;
  description?: string;
  domain: string;           // auth | schema | api | realtime | storage | gateway | ui | infra
  type: string;             // unit | integration | e2e | smoke | contract
  layer: string;            // backend | frontend | infra | full-stack
  priority: string;         // P0 | P1 | P2 | P3
  tags?: string[];
  service?: string;
  component?: string;
  environment?: string[];
  dependencies?: string[];
  preconditions?: string[];
  steps?: Array<{ order: number; action: string; via?: string }>;
  expected: {
    statusCode?: number;
    bodyContains?: string[];
    jwtClaims?: Record<string, unknown>;
    cookieSet?: string;
    [key: string]: unknown;
  };
  url?: string;
  method?: string;
  headers?: Record<string, string>;
  payload?: unknown;
  script?: string;
  timeout_ms?: number;
  retries?: number;
  author?: string;
  created_at?: Date;
  updated_at?: Date;
  phase?: string;
  status: string;           // active | draft | deprecated | skipped
  notes?: string;
  last_run?: {
    run_id?: unknown;
    executed_at?: Date;
    passed?: boolean;
    duration_ms?: number;
  };
}

export interface TestResult {
  _id?: unknown;
  test_id: string;
  suite_id?: unknown;
  run_by: string;           // ci-pipeline | developer | cron
  environment: string;
  executed_at: Date;
  passed: boolean;
  duration_ms: number;
  http_status?: number;
  response_snapshot?: unknown;
  error?: string | null;
  git_sha?: string;
  runner_version?: string;
}

export interface TestSuite {
  _id?: unknown;
  name: string;
  description?: string;
  test_ids: string[];
  phase?: string;
  created_at?: Date;
}

export interface TestEnvironment {
  _id?: unknown;
  name: string;             // local | staging | production
  kong_url: string;
  gotrue_url: string;
  postgrest_url: string;
  realtime_url: string;
  minio_url: string;
  frontend_url: string;
}

export interface TestHub {
  tests: Collection<TestDefinition>;
  results: Collection<TestResult>;
  suites: Collection<TestSuite>;
  environments: Collection<TestEnvironment>;
}

// ── Singleton connection ─────────────────────────────────────────────────────

let client: MongoClient | null = null;
let db: Db | null = null;

export async function connect(): Promise<MongoClient> {
  if (client) return client;

  const uri = process.env.MONGO_URI;
  if (!uri) {
    throw new Error(
      "MONGO_URI is not set. Copy .env.example to .env and set the value."
    );
  }

  client = new MongoClient(uri);
  await client.connect();
  db = client.db(); // uses the db name from the URI (test_hub)
  return client;
}

export async function getDb(): Promise<TestHub> {
  if (!db) await connect();
  const database = db as Db;

  return {
    tests:        database.collection<TestDefinition>("tests"),
    results:      database.collection<TestResult>("results"),
    suites:       database.collection<TestSuite>("suites"),
    environments: database.collection<TestEnvironment>("environments"),
  };
}

export async function disconnect(): Promise<void> {
  if (client) {
    await client.close();
    client = null;
    db = null;
  }
}