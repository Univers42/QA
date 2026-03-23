import { connect, disconnect, getDb, TestDefinition, TestResult } from "../../scripts/db";

// ── Types ────────────────────────────────────────────────────────────────────

interface RunResult {
  test: TestDefinition;
  passed: boolean;
  statusCode: number | null;
  duration_ms: number;
  error: string | null;
}

// ── CLI arguments ─────────────────────────────────────────────────────────────

function getArgs(): { domain?: string; priority?: string; env: string } {
  const args: Record<string, string> = {};
  for (const arg of process.argv.slice(2)) {
    const [key, value] = arg.replace("--", "").split("=");
    if (key && value) args[key] = value;
  }
  return {
    domain:   args["domain"]   ?? process.env["DOMAIN"],
    priority: args["priority"] ?? process.env["PRIORITY"],
    env:      args["env"]      ?? process.env["TEST_ENV"] ?? "local",
  };
}

// ── HTTP executor ─────────────────────────────────────────────────────────────

async function executeTest(test: TestDefinition): Promise<RunResult> {
  if (!test.url || !test.method) {
    return {
      test,
      passed: false,
      statusCode: null,
      duration_ms: 0,
      error: "Missing url or method in test definition",
    };
  }

  const start = Date.now();

  try {
    const options: RequestInit = {
      method: test.method,
      headers: (test.headers as Record<string, string>) ?? {},
    };

    if (test.payload && ["POST", "PUT", "PATCH"].includes(test.method)) {
      options.body = JSON.stringify(test.payload);
      (options.headers as Record<string, string>)["Content-Type"] =
  		(options.headers as Record<string, string>)["Content-Type"] ?? "application/json";
    }

    const response = await fetch(test.url, options);
    const duration_ms = Date.now() - start;
    const bodyText = await response.text();

    // ── Check statusCode ──────────────────────────────────────────────────────
    let passed = true;
    const errors: string[] = [];

    if (test.expected.statusCode !== undefined) {
      if (response.status !== test.expected.statusCode) {
        passed = false;
        errors.push(`expected status ${test.expected.statusCode}, got ${response.status}`);
      }
    }

    // ── Check bodyContains ────────────────────────────────────────────────────
    if (test.expected.bodyContains && test.expected.bodyContains.length > 0) {
      for (const fragment of test.expected.bodyContains) {
        if (!bodyText.includes(fragment)) {
          passed = false;
          errors.push(`body missing: "${fragment}"`);
        }
      }
    }

    return {
      test,
      passed,
      statusCode: response.status,
      duration_ms,
      error: errors.length > 0 ? errors.join(" | ") : null,
    };
  } catch (err) {
    return {
      test,
      passed: false,
      statusCode: null,
      duration_ms: Date.now() - start,
      error: `Network error: ${(err as Error).message}`,
    };
  }
}

// ── Table printer ─────────────────────────────────────────────────────────────

function printResults(results: RunResult[]): void {
  const passed = results.filter((r) => r.passed).length;
  const failed = results.filter((r) => !r.passed).length;

  console.log("\n  ┌─────────────────────────────────────────────────────────────────┐");
  console.log("  │  Prismatica QA — Test Results                                   │");
  console.log("  └─────────────────────────────────────────────────────────────────┘\n");

  for (const r of results) {
    const icon    = r.passed ? "  ✓ " : "  ✗ ";
    const id      = r.test.id.padEnd(14);
    const status  = r.statusCode !== null ? `[${r.statusCode}]` : "[???]";
    const time    = `${r.duration_ms}ms`.padStart(7);
    const title   = r.test.title.slice(0, 52);

    console.log(`${icon} ${id} ${status.padEnd(6)} ${time}  ${title}`);

    if (!r.passed && r.error) {
      console.log(`       ${"".padEnd(14)} ${r.error}`);
    }
  }

  console.log("\n  ──────────────────────────────────────────────────────────────────");
  console.log(`  Passed : ${passed}`);
  console.log(`  Failed : ${failed}`);
  console.log(`  Total  : ${results.length}`);
  console.log("  ──────────────────────────────────────────────────────────────────\n");

  if (failed > 0) process.exit(1);
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  const { domain, priority, env } = getArgs();

  console.log("\n  Prismatica QA — Runner starting...");
  if (domain)   console.log(`  Filter: domain   = ${domain}`);
  if (priority) console.log(`  Filter: priority = ${priority}`);
  console.log(`  Environment      : ${env}\n`);

  await connect();
  const { tests } = await getDb();

  // Build MongoDB filter
  const filter: Record<string, unknown> = { status: "active" };
  if (domain)   filter["domain"]   = domain;
  if (priority) filter["priority"] = priority;

  const testDocs = await tests.find(filter).toArray();

  if (testDocs.length === 0) {
    console.log("  ⚠  No active tests found for the given filters.\n");
    await disconnect();
    return;
  }

  console.log(`  Found ${testDocs.length} active test(s). Running...\n`);

  const results: RunResult[] = [];
  for (const test of testDocs) {
    const result = await executeTest(test);
    const icon = result.passed ? "  ✓" : "  ✗";
    process.stdout.write(`${icon}  ${test.id.padEnd(14)} ${test.title.slice(0, 50)}\n`);
    results.push(result);
  }

  printResults(results);
  await disconnect();
}

main().catch((err) => {
  console.error("\n  Runner failed:", err.message);
  process.exit(1);
});