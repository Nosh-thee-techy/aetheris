// Deploy Aetheris to Sepolia, commit the payout policy, and sign the one claim
// the measurements support. Then write web/data/deployment.json for the page.
//
//   node deploy_testnet.mjs --check    show addresses, balances and what is missing; sends nothing
//   node deploy_testnet.mjs            deploy for real
//
// Secrets: keys are read from the repo-root .env (gitignored). They are never printed.
// Assumption: only the resolver/deployer wallet is funded by a faucet. This script
// tops up the other wallets from it, so one faucet request is enough.
//
// Honesty notes baked into the data it writes:
//   - the only claim signed is Kabonyo Kanyagwal, the one place where the frozen
//     rule fired on measured data. Nothing is signed for the other six places.
//   - the beneficiary addresses are PLACEHOLDERS derived from a hash. Nobody holds
//     a key for them, so a demo release would be stuck, which is the safe failure.

import { readFileSync, writeFileSync, appendFileSync, mkdirSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { spawnSync } from "node:child_process";
import {
  JsonRpcProvider, FetchRequest, Network, Wallet, ContractFactory, parseEther, formatEther, keccak256, toUtf8Bytes, getAddress,
} from "ethers";
import { compile } from "./compile.mjs";
import { ruleId, thresholdsHash, zoneId, weekId, evidenceRadar, evidenceRainfall, SCENE_ITEM, WEEK } from "./ids.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
const ENV = join(ROOT, ".env");
const OUT = join(ROOT, "web", "data", "deployment.json");
const CHECK = process.argv.includes("--check");
const FORCE = process.argv.includes("--force");

const ZONES = {
  "kabonyo-kanyagwal": "Kabonyo Kanyagwal", ahero: "Ahero", ombeyi: "Ombeyi", kobura: "Kobura",
  "kakola-ombaka": "Kakola Ombaka", nyamasao: "Nyamasao", kadibo: "Kadibo",
};
const GRANT = parseEther("0.001");
const DEPOSIT = parseEther("0.02");
// Lean budget. Each attester needs its 0.01 ETH bond (one claim is signed) plus a little gas;
// the funder needs the 0.02 ETH pool plus a little gas. The contract constants are unchanged.
const TOPUP = { radar: parseEther("0.011"), rainfall: parseEther("0.011"), funder: parseEther("0.022") };
// Top-ups (0.044) plus headroom for two deploys and a dozen calls. Sepolia gas is tiny at the
// time of writing; if it spikes, send more ETH rather than lowering the bond or the pool.
const DEPLOYER_MIN = parseEther("0.05");

function readEnv() {
  const values = {};
  for (const line of readFileSync(ENV, "utf8").split(/\r?\n/)) {
    const m = line.match(/^([A-Z_]+)=(.*)$/);
    if (m) values[m[1]] = m[2].trim();
  }
  return values;
}

function ensureFunder(env) {
  if (env.FUNDER_PRIVATE_KEY) return env;
  const wallet = Wallet.createRandom();
  appendFileSync(ENV, `\nFUNDER=${wallet.address}\nFUNDER_PRIVATE_KEY=${wallet.privateKey}\n`);
  return readEnv();
}

if (!existsSync(ENV)) {
  console.error("No .env at the repo root. Run: python -m backtest.pipeline.keys");
  process.exit(1);
}
let env = readEnv();
if (!CHECK) env = ensureFunder(env);

const request = new FetchRequest(env.SEPOLIA_RPC_URL || "https://ethereum-sepolia-rpc.publicnode.com");
request.setHeader("User-Agent", "aetheris-deploy/1.0");
const provider = new JsonRpcProvider(request, Network.from(11155111), { staticNetwork: true });

const need = (name) => {
  if (!env[name]) throw new Error(`${name} missing from .env`);
  return env[name];
};
const deployer = new Wallet(need("DEPLOYER_PRIVATE_KEY"), provider); // also the resolver
const radar = new Wallet(need("RADAR_ATTESTER_PRIVATE_KEY"), provider);
const rainfall = new Wallet(need("RAINFALL_ATTESTER_PRIVATE_KEY"), provider);
const funder = env.FUNDER_PRIVATE_KEY ? new Wallet(env.FUNDER_PRIVATE_KEY, provider) : null;

if (deployer.address.toLowerCase() !== need("RESOLVER").toLowerCase()) {
  throw new Error("DEPLOYER_PRIVATE_KEY is not the RESOLVER address in .env");
}

const balance = async (address) => await provider.getBalance(address);
const have = await balance(deployer.address);

console.log("Network: Sepolia (11155111)");
console.log("Resolver and deployer:", deployer.address, formatEther(have), "ETH");
console.log("Radar attester:       ", radar.address, formatEther(await balance(radar.address)), "ETH");
console.log("Rainfall attester:    ", rainfall.address, formatEther(await balance(rainfall.address)), "ETH");
if (funder) console.log("Funder:               ", funder.address, formatEther(await balance(funder.address)), "ETH");

if (have < DEPLOYER_MIN) {
  console.log(`\nNOT READY. Send at least ${formatEther(DEPLOYER_MIN)} Sepolia ETH to ${deployer.address}.`);
  console.log("That one address funds the other wallets. A faucet request needs a human, so this cannot be automated.");
  process.exit(CHECK ? 2 : 1);
}
if (CHECK) {
  console.log("\nREADY. Run without --check to deploy.");
  process.exit(0);
}
if (existsSync(OUT) && !FORCE) {
  console.error("web/data/deployment.json already exists. Use --force to deploy again.");
  process.exit(1);
}

const send = async (label, promise) => {
  const tx = await promise;
  const receipt = await tx.wait();
  console.log(`${label}: ${receipt.hash}`);
  return receipt;
};

// Top up the other wallets from the deployer.
for (const [name, wallet, amount] of [["radar", radar, TOPUP.radar], ["rainfall", rainfall, TOPUP.rainfall], ["funder", funder, TOPUP.funder]]) {
  if ((await balance(wallet.address)) < amount) {
    await send(`fund ${name}`, deployer.sendTransaction({ to: wallet.address, value: amount }));
  }
}

const built = compile();
const rule = ruleId();
const thresholds = thresholdsHash();

const triggerFactory = new ContractFactory(built.FloodTrigger.abi, built.FloodTrigger.bytecode, deployer);
const trigger = await triggerFactory.deploy(rule, thresholds, deployer.address, radar.address, [rainfall.address], need("POOL"));
const triggerReceipt = await trigger.deploymentTransaction().wait();
console.log("FloodTrigger:", await trigger.getAddress());

const seasonEnd = Number(env.SEASON_END) || Math.floor(Date.UTC(2026, 11, 31) / 1000);
const escrowFactory = new ContractFactory(built.PayoutEscrow.abi, built.PayoutEscrow.bytecode, deployer);
const escrow = await escrowFactory.deploy(await trigger.getAddress(), funder.address, seasonEnd);
const escrowReceipt = await escrow.deploymentTransaction().wait();
console.log("PayoutEscrow:", await escrow.getAddress());

// Policy: committed once, before any claim can be paid.
const escrowAsFunder = escrow.connect(funder);
for (const slug of Object.keys(ZONES)) {
  const placeholder = getAddress("0x" + keccak256(toUtf8Bytes(`aetheris-demo-beneficiary:${slug}`)).slice(26));
  await send(`grant ${slug}`, escrowAsFunder.addGrant(zoneId(slug), placeholder, GRANT));
}
await send("commit policy", escrowAsFunder.commitPolicy());
await send("deposit", escrowAsFunder.deposit({ value: DEPOSIT }));

// The one claim the data supports: radar and rainfall both measured above the frozen lines.
const zone = zoneId("kabonyo-kanyagwal");
const week = weekId(WEEK);
const radarEvidence = evidenceRadar(SCENE_ITEM);
const rainEvidence = evidenceRainfall("2024-05-04", "2024-05-06");
const bond = await trigger.ATTESTER_BOND();
await send("radar signs", trigger.connect(radar).attest(zone, week, radarEvidence, { value: bond }));
await send("rainfall signs", trigger.connect(rainfall).attest(zone, week, rainEvidence, { value: bond }));

const id = await trigger.computeId(zone, week);
const claim = await trigger.getTrigger(id);
const STATES = ["None", "Proposed: challenge window open", "Challenged", "Finalized", "Rejected"];
const windowSeconds = Number(await trigger.CHALLENGE_WINDOW());
const block = await provider.getBlockNumber();

mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify({
  network: "Sepolia",
  chain_id: 11155111,
  explorer: "https://sepolia.etherscan.io",
  block,
  snapshot_at: new Date().toISOString(),
  trigger: { address: await trigger.getAddress(), tx: triggerReceipt.hash },
  escrow: { address: await escrow.getAddress(), tx: escrowReceipt.hash },
  roles: { resolver: deployer.address, radar: radar.address, rainfall: rainfall.address, pool: need("POOL"), funder: funder.address },
  rule_id: rule,
  thresholds_hash: thresholds,
  policy_hash: await escrow.policyHash(),
  season_end: seasonEnd,
  pool_balance_eth: formatEther(await provider.getBalance(await escrow.getAddress())),
  beneficiaries: "placeholder addresses derived from a hash; nobody holds a key for them",
  claims: [{
    zone: "kabonyo-kanyagwal",
    zone_name: ZONES["kabonyo-kanyagwal"],
    trigger_id: id,
    state: STATES[Number(claim.state)],
    finalizes_at: Number(claim.windowStart) + windowSeconds,
    signers: [
      { role: "Radar", address: radar.address, evidence: radarEvidence },
      { role: "Rainfall", address: rainfall.address, evidence: rainEvidence },
    ],
  }],
}, null, 2));
console.log("wrote", OUT);

const build = spawnSync("python", [join(ROOT, "web", "build.py")], { stdio: "inherit" });
process.exit(build.status ?? 0);
