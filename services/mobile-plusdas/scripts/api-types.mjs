// Generate src/api/generated/backend-ot.ts (imported as `@contracts/backend-ot`) from backend-ot's
// published OpenAPI contract.
//
//   node scripts/api-types.mjs           write the file (`make api-types`)
//   node scripts/api-types.mjs --check   fail if the committed file is stale (`make test`)
//
// CONTRACT is the ONE place this service points at contracts/ (override with BACKEND_OT_OPENAPI).
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const serviceDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const NAME = "backend-ot";
const CONTRACT = process.env.BACKEND_OT_OPENAPI ?? "../../contracts/openapi/backend-ot.openapi.json";

async function generate() {
  const header =
    `// GENERATED from contracts/openapi/${NAME}.openapi.json by scripts/api-types.mjs.\n` +
    `// Do not edit: run \`make api-types\`. Import it as \`@contracts/${NAME}\`.\n\n`;
  const ast = await openapiTS(pathToFileURL(resolve(serviceDir, CONTRACT)));
  return header + astToString(ast);
}

async function main() {
  const check = process.argv.includes("--check");
  const relative = `src/api/generated/${NAME}.ts`;
  const output = resolve(serviceDir, relative);
  const generated = await generate();
  if (!check) {
    await mkdir(dirname(output), { recursive: true });
    await writeFile(output, generated);
    console.log(`api-types: wrote ${output}`);
    return 0;
  }
  const committed = await readFile(output, "utf8").catch(() => "");
  if (committed.replace(/\r\n/g, "\n") !== generated) {
    console.error(`api-types: ${relative} is stale; run \`make api-types\``);
    return 1;
  }
  console.log(`api-types: ${relative} matches the contract`);
  return 0;
}

process.exitCode = await main();
