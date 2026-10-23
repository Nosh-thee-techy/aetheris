// Act on a claim from the command line, with the project's own keys.
//
//   node referee.mjs status    <place>
//   node referee.mjs uphold    <place>     referee only: finalize a challenged claim
//   node referee.mjs reject    <place>     referee only: slash both bonds to the challenger
//   node referee.mjs expire    <place>     anyone: let a claim stand after a silent referee
//   node referee.mjs finalize  <place>     anyone: after the 24 h window with no challenge
//   node referee.mjs release   <place>     anyone: escrow pays the committed table, once
//
// <place> is a slug from web/data/deployment.json, e.g. kabonyo-kanyagwal.
//
// Why this exists: the referee is one key. It must never be pasted into a browser
// wallet, so the pages show the referee's buttons disabled for everyone else and this
// script is how the project's own key answers a challenge.
//
// Secrets are read from the repo-root .env and are never printed. Testnet only.

import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { JsonRpcProvider, FetchRequest, Network, Wallet, Contract } from "ethers";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
const [, , action, place] = process.argv;
const ACTIONS = ["status", "uphold", "reject", "expire", "finalize", "release"];
if (!ACTIONS.includes(action) || !place) {
  console.error("usage: node referee.mjs <status|uphold|reject|expire|finalize|release> <place>");
  process.exit(1);
}

const deployment = JSON.parse(readFileSync(join(ROOT, "web", "data", "deployment.json"), "utf8"));
const config = readFileSync(join(ROOT, "web", "chain-config.js"), "utf8");
const zones = JSON.parse(config.slice(config.indexOf("{"), config.lastIndexOf("}") + 1)).zones;
if (!zones[place]) {
  console.error(`unknown place "${place}". Known: ${Object.keys(zones).join(", ")}`);
  process.exit(1);
}
const id = zones[place].claimId;

const env = {};
const envPath = join(ROOT, ".env");
if (existsSync(envPath)) {
  for (const line of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const m = line.match(/^([A-Z_]+)=(.*)$/);
    if (m) env[m[1]] = m[2].trim();
  }
}

const request = new FetchRequest(env.SEPOLIA_RPC_URL || "https://ethereum-sepolia-rpc.publicnode.com");
request.setHeader("User-Agent", "aetheris-referee/1.0");
const provider = new JsonRpcProvider(request, Network.from(11155111), { staticNetwork: true });
// The referee key is also the deployer key. Only it can uphold or reject.
const signer = env.DEPLOYER_PRIVATE_KEY ? new Wallet(env.DEPLOYER_PRIVATE_KEY, provider) : null;

const triggerAbi = [
  "function getTrigger(bytes32) view returns (tuple(bytes32 zoneId, bytes32 eventWeek, uint64 windowStart, uint64 resolveDeadline, uint8 state, address challenger, uint256 challengerStake, bool radarSigned, uint8 corroboratorCount, uint8 finalizationReason))",
  "function resolver() view returns (address)",
  "function finalize(bytes32)", "function expire(bytes32)", "function resolve(bytes32,bool)",
  "error NotResolver()", "error NoChallenge()", "error ResolveWindowOver()", "error ResolveWindowOpen()",
  "error NotReady()", "error ChallengeWindowOpen()",
];
const escrowAbi = [
  "function release(bytes32)", "function fingerprintPaid(bytes32) view returns (bool)",
  "error PolicyOpen()", "error NotFinalized()", "error AlreadyPaid()", "error FingerprintMismatch()",
  "error NoBeneficiary()", "error InsufficientPool()",
];
const trigger = new Contract(deployment.trigger.address, triggerAbi, signer ?? provider);
const escrow = new Contract(deployment.escrow.address, escrowAbi, signer ?? provider);

const STATES = ["None", "Proposed", "Challenged", "Finalized", "Rejected"];
const t = await trigger.getTrigger(id);
const block = await provider.getBlock("latest");
console.log(`${place}: ${STATES[Number(t.state)]}  (chain time ${new Date(block.timestamp * 1000).toISOString()})`);
if (t.windowStart > 0n) console.log("  challenge window closes", new Date((Number(t.windowStart) + 86400) * 1000).toISOString());
if (Number(t.state) === 2) console.log("  referee deadline      ", new Date(Number(t.resolveDeadline) * 1000).toISOString(), " challenger", t.challenger);
console.log("  paid:", await escrow.fingerprintPaid(id));
if (action === "status") process.exit(0);

if (!signer) { console.error("DEPLOYER_PRIVATE_KEY is not in .env"); process.exit(1); }
if ((action === "uphold" || action === "reject") && signer.address.toLowerCase() !== (await trigger.resolver()).toLowerCase()) {
  console.error("this key is not the referee"); process.exit(1);
}

const [target, method, args] = {
  uphold: [trigger, "resolve", [id, true]], reject: [trigger, "resolve", [id, false]],
  expire: [trigger, "expire", [id]], finalize: [trigger, "finalize", [id]], release: [escrow, "release", [id]],
}[action];
try {
  // Dry run first: an eth_call returns the contract's own refusal, a gas estimate may not.
  await target[method].staticCall(...args);
  const tx = await target[method](...args);
  console.log("submitted", tx.hash);
  await tx.wait();
  console.log("confirmed:", `${deployment.explorer}/tx/${tx.hash}`);
  console.log("now:", STATES[Number((await trigger.getTrigger(id)).state)], " paid:", await escrow.fingerprintPaid(id));
} catch (err) {
  // The contract names its refusals; show the name, not a stack trace.
  console.error("refused:", err.revert?.name || err.shortMessage || err.message);
  process.exit(1);
}
