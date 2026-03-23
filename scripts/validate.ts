import Ajv, { JSONSchemaType } from "ajv";
import * as fs from "fs";
import * as path from "path";

// ── Schema ───────────────────────────────────────────────────────────────────

const testSchema = {
  type: "object",
  required: ["id", "title", "domain", "type", "layer", "priority", "expected", "status"],
  additionalProperties: true,
  properties: {
    id: {
      type: "string",
      pattern: "^[A-Z]+-[0-9]+$",
      description: "Format: DOMAIN-NNN (e.g. AUTH-001)"
    },
    title: { type: "string", minLength: 5 },
    description: { type: "string" },
    domain: {
      type: "string",
      enum: ["auth", "schema", "api", "realtime", "storage", "gateway", "ui", "infra"]
    },
    type: {
      type: "string",
      enum: ["unit", "integration", "e2e", "smoke", "contract"]
    },
    layer: {
      type: "string",
      enum: ["backend", "frontend", "infra", "full-stack"]
    },
    priority: {
      type: "string",
      enum: ["P0", "P1", "P2", "P3"]
    },
    tags: {
      type: "array",
      items: { type: "string" }
    },
    service: { type: "string" },
    component: { type: "string" },
    environment: {
      type: "array",
      items: { type: "string" }
    },
    dependencies: {
      type: "array",
      items: { type: "string" }
    },
    preconditions: {
      type: "array",
      items: { type: "string" }
    },
    expected: {
      type: "object",
      required: [],
      additionalProperties: true,
      properties: {
        statusCode: { type: "number" },
        bodyContains: {
          type: "array",
          items: { type: "string" }
        }
      }
    },
    url: { type: "string" },
    method: {
      type: "string",
      enum: ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
    },
    timeout_ms: { type: "number", minimum: 0 },
    retries: { type: "number", minimum: 0 },
    author: { type: "string" },
    phase: { type: "string" },
    status: {
      type: "string",
      enum: ["active", "draft", "deprecated", "skipped"]
    },
    notes: { type: "string" }
  }
};

// ── File reader ──────────────────────────────────────────────────────────────

function readJsonFiles(dir: string): Array<{ file: string; data: unknown }> {
  const results: Array<{ file: string; data: unknown }> = [];

  if (!fs.existsSync(dir)) return results;

  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...readJsonFiles(fullPath));
    } else if (entry.isFile() && entry.name.endsWith(".json")) {
      try {
        const raw = fs.readFileSync(fullPath, "utf-8");
        results.push({ file: fullPath, data: JSON.parse(raw) });
      } catch (err) {
        results.push({ file: fullPath, data: null });
        console.error(`  ✗  Parse error: ${fullPath}`);
        console.error(`     ${(err as Error).message}`);
      }
    }
  }

  return results;
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function validate(): Promise<void> {
  const definitionsDir = path.resolve(__dirname, "../test-definitions");
  const ajv = new Ajv({ allErrors: true });
  const validateFn = ajv.compile(testSchema);

  console.log("\n  Validating test definitions...\n");

  const files = readJsonFiles(definitionsDir);

  if (files.length === 0) {
    console.log("  ⚠  No JSON files found in test-definitions/\n");
    return;
  }

  let passed = 0;
  let failed = 0;

  for (const { file, data } of files) {
    const relativePath = path.relative(process.cwd(), file);

    if (data === null) {
      failed++;
      continue;
    }

    const valid = validateFn(data);

    if (valid) {
      const doc = data as Record<string, unknown>;
      console.log(`  +  OK       ${String(doc.id ?? "?").padEnd(14)}  ${relativePath}`);
      passed++;
    } else {
      const doc = data as Record<string, unknown>;
      console.log(`  ✗  INVALID  ${String(doc.id ?? "?").padEnd(14)}  ${relativePath}`);
      for (const err of validateFn.errors ?? []) {
        const field = err.instancePath || err.schemaPath;
        console.log(`             ${field}: ${err.message}`);
      }
      failed++;
    }
  }

  console.log("\n  -------------------------------------------");
  console.log(`  Valid   : ${passed}`);
  console.log(`  Invalid : ${failed}`);
  console.log(`  Total   : ${files.length}`);
  console.log("  -------------------------------------------\n");

  if (failed > 0) {
    console.error(`  Fix the errors above before running make seed.\n`);
    process.exit(1);
  }
}

validate().catch((err) => {
  console.error("\n  Validation failed:", err.message);
  process.exit(1);
});