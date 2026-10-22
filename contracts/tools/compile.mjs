// Compile the contracts with solc-js 0.8.24, the version in foundry.toml.
//
// Why this exists: it lets anyone with Node check that the contracts build and
// deploy them, without installing Foundry. `forge test` stays the test suite.
// Assumption: contracts only import each other by relative path.

import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const solc = require("solc");
const SRC = join(dirname(fileURLToPath(import.meta.url)), "..", "src");
const FILES = ["IFloodResolver.sol", "FloodTrigger.sol", "PayoutEscrow.sol"];

/** Returns { FloodTrigger: {abi, bytecode}, PayoutEscrow: {abi, bytecode} }. Throws on any compile error. */
export function compile() {
  const sources = Object.fromEntries(
    FILES.map((name) => [name, { content: readFileSync(join(SRC, name), "utf8") }]),
  );
  const input = {
    language: "Solidity",
    sources,
    settings: {
      optimizer: { enabled: true, runs: 200 },
      outputSelection: { "*": { "*": ["abi", "evm.bytecode.object"] } },
    },
  };
  const output = JSON.parse(solc.compile(JSON.stringify(input)));
  const errors = (output.errors ?? []).filter((e) => e.severity === "error");
  if (errors.length) {
    throw new Error(errors.map((e) => e.formattedMessage).join("\n"));
  }
  const pick = (file, name) => ({
    abi: output.contracts[file][name].abi,
    bytecode: "0x" + output.contracts[file][name].evm.bytecode.object,
  });
  return {
    FloodTrigger: pick("FloodTrigger.sol", "FloodTrigger"),
    PayoutEscrow: pick("PayoutEscrow.sol", "PayoutEscrow"),
    warnings: (output.errors ?? []).filter((e) => e.severity !== "error").map((e) => e.formattedMessage),
  };
}

if (import.meta.url === `file://${process.argv[1].replace(/\\/g, "/")}` || process.argv[1]?.endsWith("compile.mjs")) {
  const built = compile();
  const out = join(dirname(fileURLToPath(import.meta.url)), "build");
  mkdirSync(out, { recursive: true });
  for (const name of ["FloodTrigger", "PayoutEscrow"]) {
    writeFileSync(join(out, `${name}.json`), JSON.stringify(built[name]));
    console.log(`${name}: ${(built[name].bytecode.length - 2) / 2} bytes of bytecode`);
  }
  for (const w of built.warnings) console.log("warning:", w.split("\n")[0]);
  console.log("compiled with solc", solc.version());
}
