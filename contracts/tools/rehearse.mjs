// Rehearse the whole flow on an in-process chain before spending testnet ETH.
//
// What this proves: the compiled contracts do what the README says, end to end,
// including the refusals. What it does not prove: anything about a public network.
// It does not replace `forge test`; it is a second, independent check.

import ganache from "ganache";
import { BrowserProvider, ContractFactory, parseEther, keccak256, toUtf8Bytes } from "ethers";
import { compile } from "./compile.mjs";
import { ruleId, thresholdsHash, zoneId, weekId, evidenceRadar, evidenceRainfall, SCENE_ITEM, WEEK } from "./ids.mjs";

const built = compile();
const chain = ganache.provider({
  wallet: { totalAccounts: 8, defaultBalance: 1000 },
  logging: { quiet: true },
  chain: { allowUnlimitedContractSize: false },
});
const provider = new BrowserProvider(chain);
const signers = await Promise.all([0, 1, 2, 3, 4, 5, 6].map((i) => provider.getSigner(i)));
const [resolver, radar, rainfall, pool, funder, stranger, beneficiary] = signers;

let passed = 0;
const failed = [];
function check(name, ok) {
  if (ok) passed += 1;
  else failed.push(name);
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}`);
}
async function reverts(name, work, errorName) {
  try {
    await work();
    check(name, false);
  } catch (e) {
    const text = [e.revert?.name, e.shortMessage, e.message, JSON.stringify(e.data ?? "")].join(" ");
    check(name, text.includes(errorName));
  }
}
const warp = async (seconds) => {
  await chain.request({ method: "evm_increaseTime", params: [seconds] });
  await chain.request({ method: "evm_mine", params: [] });
};

const deploy = async (name, signer, ...args) => {
  const factory = new ContractFactory(built[name].abi, built[name].bytecode, signer);
  const contract = await factory.deploy(...args);
  await contract.waitForDeployment();
  return contract;
};

const zone = zoneId("kabonyo-kanyagwal");
const other = zoneId("ahero");
const week = weekId(WEEK);
const radarEvidence = evidenceRadar(SCENE_ITEM);
const rainEvidence = evidenceRainfall("2024-05-04", "2024-05-06");
const bond = parseEther("0.01");

async function fresh() {
  const trigger = await deploy(
    "FloodTrigger", resolver, ruleId(), thresholdsHash(),
    await resolver.getAddress(), await radar.getAddress(), [await rainfall.getAddress()], await pool.getAddress(),
  );
  const season = (await provider.getBlock("latest")).timestamp + 30 * 86400;
  const escrow = await deploy("PayoutEscrow", funder, await trigger.getAddress(), await funder.getAddress(), season);
  return { trigger, escrow, season };
}
const as = (contract, signer) => contract.connect(signer);

// ---- constructor guards
{
  const radarAddress = await radar.getAddress();
  const rainAddress = await rainfall.getAddress();
  const poolAddress = await pool.getAddress();
  await reverts(
    "constructor rejects a resolver who is also an attester",
    () => deploy("FloodTrigger", resolver, ruleId(), thresholdsHash(), radarAddress, radarAddress, [rainAddress], poolAddress),
    "ResolverIsAttester",
  );
}

// ---- the quorum
let { trigger, escrow, season } = await fresh();
const id = await trigger.computeId(zone, week);
await as(trigger, rainfall).attest(zone, week, rainEvidence, { value: bond });
check("rainfall alone does not open the window", (await trigger.getTrigger(id)).windowStart === 0n);
await reverts("rainfall alone cannot be challenged", () => as(trigger, stranger).challenge(id, { value: bond }), "NotChallengeable");
await as(trigger, radar).attest(zone, week, radarEvidence, { value: bond });
check("radar plus rainfall opens the window", (await trigger.getTrigger(id)).windowStart > 0n);
await reverts("a second signature from the same attester is blocked", () =>
  as(trigger, radar).attest(zone, week, keccak256(toUtf8Bytes("different")), { value: bond }), "AlreadySigned");
await reverts("a stranger cannot sign", () => as(trigger, stranger).attest(zone, week, radarEvidence, { value: bond }), "NotAttester");
await reverts("the resolver cannot sign", () => as(trigger, resolver).attest(zone, week, radarEvidence, { value: bond }), "NotAttester");
check("each attester keeps its own evidence hash",
  (await trigger.evidenceOf(id, await radar.getAddress())) === radarEvidence &&
  (await trigger.evidenceOf(id, await rainfall.getAddress())) === rainEvidence);
await reverts("finalize before the window ends reverts", () => trigger.finalize(id), "ChallengeWindowOpen");

// ---- radar alone never opens
const lone = await trigger.computeId(other, week);
await as(trigger, radar).attest(other, week, radarEvidence, { value: bond });
check("radar alone does not open the window", (await trigger.getTrigger(lone)).windowStart === 0n);

// ---- escrow policy, then release
await as(escrow, funder).addGrant(zone, await beneficiary.getAddress(), parseEther("0.002"));
await as(escrow, funder).addGrant(other, await stranger.getAddress(), parseEther("0.002"));
await as(escrow, funder).commitPolicy();
const funderAddress = await funder.getAddress();
await reverts("the policy cannot change after it is committed", () =>
  as(escrow, funder).addGrant(zone, funderAddress, 1n), "PolicyLocked");
await as(escrow, funder).deposit({ value: parseEther("0.02") });
await reverts("release before Finalized reverts", () => escrow.release(id), "NotFinalized");

await warp(24 * 3600 + 1);
await trigger.finalize(id);
await escrow.release(id);
check("release credits the committed beneficiary",
  (await escrow.withdrawable(await beneficiary.getAddress())) === parseEther("0.002"));
check("a place that did not finalize is not paid", (await escrow.withdrawable(await stranger.getAddress())) === 0n);
await reverts("a second release of the same claim reverts", () => escrow.release(id), "AlreadyPaid");
const before = await provider.getBalance(await beneficiary.getAddress());
await as(escrow, beneficiary).withdraw();
check("the beneficiary can pull the payout", (await provider.getBalance(await beneficiary.getAddress())) > before);
await reverts("a wrong address has nothing to withdraw", () => as(escrow, stranger).withdraw(), "NothingToWithdraw");
await reverts("the funder cannot reclaim mid-season", () => as(escrow, funder).reclaim(), "SeasonOpen");
check("attester bonds are credited on finalization", (await trigger.withdrawable(await radar.getAddress())) >= bond);
await as(trigger, radar).withdraw();
check("an attester can pull its bond back", (await trigger.withdrawable(await radar.getAddress())) === 0n);

// ---- challenge paths
({ trigger, escrow } = await fresh());
const id2 = await trigger.computeId(zone, week);
await as(trigger, radar).attest(zone, week, radarEvidence, { value: bond });
await as(trigger, rainfall).attest(zone, week, rainEvidence, { value: bond });
await as(trigger, stranger).challenge(id2, { value: bond });
await reverts("only the resolver can resolve", () => as(trigger, stranger).resolve(id2, true), "NotResolver");
await as(trigger, resolver).resolve(id2, false);
check("a rejected claim slashes both bonds to the challenger",
  (await trigger.withdrawable(await stranger.getAddress())) === bond * 3n);
check("a rejected claim is not Finalized", (await trigger.getTrigger(id2)).state === 4n);

({ trigger, escrow } = await fresh());
const id3 = await trigger.computeId(zone, week);
await as(trigger, radar).attest(zone, week, radarEvidence, { value: bond });
await as(trigger, rainfall).attest(zone, week, rainEvidence, { value: bond });
await as(trigger, stranger).challenge(id3, { value: bond });
await warp(48 * 3600 + 1);
await reverts("the resolver cannot act after its deadline", () => as(trigger, resolver).resolve(id3, false), "ResolveWindowOver");
await trigger.expire(id3);
check("a silent resolver lets the claim stand", (await trigger.getTrigger(id3)).state === 3n);

// ---- reclaim after the season
({ trigger, escrow, season } = await fresh());
await as(escrow, funder).addGrant(zone, await beneficiary.getAddress(), parseEther("0.002"));
await as(escrow, funder).commitPolicy();
await as(escrow, funder).deposit({ value: parseEther("0.02") });
await warp(31 * 86400);
await as(escrow, funder).reclaim();
check("the funder can reclaim unspent funds after the season",
  (await escrow.withdrawable(await funder.getAddress())) === parseEther("0.02"));

console.log(`\n${passed} passed, ${failed.length} failed`);
if (failed.length) {
  console.log("failed:", failed.join("; "));
  process.exit(1);
}
process.exit(0);
