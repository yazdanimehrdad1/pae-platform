// Generate src/api/generated/backend-ot.ts from backend-ot's published OpenAPI contract.
//
//   node scripts/api-types.mjs           write the file (`make api-types`)
//   node scripts/api-types.mjs --check   fail if the committed file is stale (`make test`)
//
// CONTRACT is the ONE place this service points at contracts/. When this service is extracted
// into its own repo and contracts/ becomes a published package, change it here (or set
// BACKEND_OT_OPENAPI) and nothing in src/ changes: the code imports `@contracts/backend-ot`.
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const serviceDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const CONTRACT = resolve(
  serviceDir,
  process.env.BACKEND_OT_OPENAPI ?? "../../contracts/openapi/backend-ot.openapi.json",
);
const OUTPUT = resolve(serviceDir, "src/api/generated/backend-ot.ts");
const HEADER =
  "// GENERATED from contracts/openapi/backend-ot.openapi.json by scripts/api-types.mjs.\n" +
  "// Do not edit: run `make api-types`. Import it as `@contracts/backend-ot`.\n\n";

async function main() {
  const ast = await openapiTS(pathToFileURL(CONTRACT));
  const generated = HEADER + astToString(ast);

  if (!process.argv.includes("--check")) {
    await mkdir(dirname(OUTPUT), { recursive: true });
    await writeFile(OUTPUT, generated);
    console.log(`api-types: wrote ${OUTPUT}`);
    return 0;
  }

  const committed = await readFile(OUTPUT, "utf8").catch(() => "");
  if (committed.replace(/\r\n/g, "\n") !== generated) {
    console.error("api-types: src/api/generated/backend-ot.ts is stale; run `make api-types`");
    return 1;
  }
  console.log("api-types: src/api/generated/backend-ot.ts matches the contract");
  return 0;
}

// exitCode, not process.exit(): see scripts/check_same_origin.mjs.
process.exitCode = await main();
