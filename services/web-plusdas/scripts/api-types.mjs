// Generate the API types in src/api/generated/ from the published OpenAPI contracts:
// backend-ot (backend-ot.ts, imported as `@contracts/backend-ot`) and the powerflow simulator
// (powerflow.ts, imported as `@contracts/powerflow`).
//
//   node scripts/api-types.mjs           write the files (`make api-types`)
//   node scripts/api-types.mjs --check   fail if a committed file is stale (`make test`)
//
// CONTRACTS is the ONE place this service points at contracts/. When this service is extracted
// into its own repo and contracts/ becomes a published package, change it here (or set
// BACKEND_OT_OPENAPI / POWERFLOW_OPENAPI) and nothing in src/ changes.
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const serviceDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const CONTRACTS = [
  {
    name: "backend-ot",
    contract: process.env.BACKEND_OT_OPENAPI ?? "../../contracts/openapi/backend-ot.openapi.json",
  },
  {
    name: "powerflow",
    contract: process.env.POWERFLOW_OPENAPI ?? "../../contracts/openapi/powerflow.openapi.json",
  },
];

async function generate({ name, contract }) {
  const header =
    `// GENERATED from contracts/openapi/${name}.openapi.json by scripts/api-types.mjs.\n` +
    `// Do not edit: run \`make api-types\`. Import it as \`@contracts/${name}\`.\n\n`;
  const ast = await openapiTS(pathToFileURL(resolve(serviceDir, contract)));
  return header + astToString(ast);
}

async function main() {
  const check = process.argv.includes("--check");
  let failed = 0;
  for (const entry of CONTRACTS) {
    const output = resolve(serviceDir, `src/api/generated/${entry.name}.ts`);
    const relative = `src/api/generated/${entry.name}.ts`;
    const generated = await generate(entry);
    if (!check) {
      await mkdir(dirname(output), { recursive: true });
      await writeFile(output, generated);
      console.log(`api-types: wrote ${output}`);
      continue;
    }
    const committed = await readFile(output, "utf8").catch(() => "");
    if (committed.replace(/\r\n/g, "\n") !== generated) {
      console.error(`api-types: ${relative} is stale; run \`make api-types\``);
      failed = 1;
    } else {
      console.log(`api-types: ${relative} matches the contract`);
    }
  }
  return failed;
}

// exitCode, not process.exit(): see scripts/check_same_origin.mjs.
process.exitCode = await main();
