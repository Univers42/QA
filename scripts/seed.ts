import * as fs from "fs";
import * as path from "path";
import { connect, disconnect, getDb, TestDefinition } from "./db";

// ── Config ───────────────────────────────────────────────────────────────────

const DEFINITIONS_DIR = path.resolve(__dirname, "../test-definitions");

const REQUIRED_FIELDS: (keyof TestDefinition)[] = [
  "id",
  "title",
  "domain",
  "type",
  "layer",
  "priority",
  "expected",
  "status",
];

// ── Helpers ──────────────────────────────────────────────────────────────────

function readJsonFiles(dir: string): Array<{ file: string; data: unknown }> {
  const results: Array<{ file: string; data: unknown }> = [];

  if (!fs.existsSync(dir)) {
    console.warn(`  ⚠  Directory not found: ${dir}`);
    return results;
  }

  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);

    if (entry.isDirectory()) {
      results.push(...readJsonFiles(fullPath));
    } else if (entry.isFile() && entry.name.endsWith(".json")) {
      try {
        const raw = fs.readFileSync(fullPath, "utf-8");
        const data = JSON.parse(raw);
        results.push({ file: fullPath, data });
      } catch (err) {
        console.error(`  ✗  Failed to parse ${fullPath}: ${(err as Error).message}`);
      }
    }
  }

  return results;
}

function validate(data: unknown, file: string): data is TestDefinition {
  if (typeof data !== "object" || data === null) {
    console.error(`  ✗  ${file}: not a JSON object`);
    return false;
  }

  const doc = data as Record<string, unknown>;
  const missing = REQUIRED_FIELDS.filter(
    (f) => !(f in doc) || doc[f] === undefined
  );

  if (missing.length > 0) {
    console.error(
      `  ✗  ${file}: missing required fields: ${missing.join(", ")}`
    );
    return false;
  }

  return true;
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function seed(): Promise<void> {
  console.log("\n  Seeding test definitions into MongoDB...\n");

  await connect();
  const { tests } = await getDb();

  const files = readJsonFiles(DEFINITIONS_DIR);

  if (files.length === 0) {
    console.log("  ⚠  No JSON files found in test-definitions/");
    console.log("     Add your first test and run make seed again.\n");
    await disconnect();
    return;
  }

  let inserted = 0;
  let updated = 0;
  let skipped = 0;

  for (const { file, data } of files) {
    const relativePath = path.relative(process.cwd(), file);

    if (!validate(data, relativePath)) {
      skipped++;
      continue;
    }

    const doc: TestDefinition = {
      ...data,
      created_at: data.created_at
  		? new Date(data.created_at as unknown as string)
  		: new Date(),
      updated_at: new Date(),
    };

    const result = await tests.updateOne(
      { id: doc.id },
      { $set: doc },
      { upsert: true }
    );

    if (result.upsertedCount > 0) {
      console.log(`  +  Inserted  ${doc.id.padEnd(12)}  ${doc.title}`);
      inserted++;
    } else if (result.modifiedCount > 0) {
      console.log(`  ~  Updated   ${doc.id.padEnd(12)}  ${doc.title}`);
      updated++;
    } else {
      console.log(`  -  No change ${doc.id.padEnd(12)}  ${doc.title}`);
    }
  }

  console.log("\n  -------------------------------------------");
  console.log(`  Inserted : ${inserted}`);
  console.log(`  Updated  : ${updated}`);
  console.log(`  Skipped  : ${skipped} (validation errors)`);
  console.log(`  Total    : ${files.length}`);
  console.log("  -------------------------------------------\n");

  await disconnect();
}

seed().catch((err) => {
  console.error("\n  Seed failed:", err.message);
  process.exit(1);
});