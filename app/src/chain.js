/**
 * Sepolia reads and wallet writes. Holds no keys.
 * If the RPC fails, callers keep the deploy snapshot and say so.
 */
import {
  BrowserProvider,
  Contract,
  JsonRpcProvider,
  Network,
  formatEther,
  parseEther,
} from "ethers";

export const CHAIN = {
  chainId: 11155111,
  chainName: "Sepolia",
  rpcs: [
    "https://ethereum-sepolia-rpc.publicnode.com",
    "https://sepolia.drpc.org",
  ],
  explorer: "https://sepolia.etherscan.io",
  trigger: "0xFE35E6F742e7bdD2864AB753035F82047399E3D2",
  escrow: "0x70A0c3A7Fbd36d9E822CC11c19a7fD5B7b98A7d1",
  snapshotBlock: 11974896,
  challengeWindow: 86400,
  resolveWindow: 172800,
  stakeEth: "0.01",
  roles: {
    resolver: "0x7879c568aaA7EB06D8c4Eb54EBd0dd45CC3E9d54",
    radar: "0x2C9D987c43c21D444abE3760445B755A1Ac5224a",
    rainfall: "0xDaeC50e751f97FCf85F61d724ed522887C94b7a4",
  },
  zones: {
    "kabonyo-kanyagwal": {
      name: "Kabonyo Kanyagwal",
      zoneId: "0xc539b24ae66e6056f410ec7a2a9df42022e9411541a5d39d2e14402be5ce2a6e",
      claimId: "0x97b3fdcca00b1583d76d1c2a7f7679843893b6c88bc7951631223067e9196ff0",
    },
  },
};

const TRIGGER_ABI = [
  "function getTrigger(bytes32 id) view returns (tuple(bytes32 zoneId, bytes32 eventWeek, uint64 windowStart, uint64 resolveDeadline, uint8 state, address challenger, uint256 challengerStake, bool radarSigned, uint8 corroboratorCount, uint8 finalizationReason))",
  "function signersOf(bytes32 id) view returns (address[])",
  "function evidenceOf(bytes32 id, address who) view returns (bytes32)",
  "function withdrawable(address who) view returns (uint256)",
  "function challenge(bytes32 id) payable",
  "function finalize(bytes32 id)",
  "function expire(bytes32 id)",
  "function resolve(bytes32 id, bool upheld)",
  "function withdraw()",
];

const ESCROW_ABI = [
  "function policyLocked() view returns (bool)",
  "function deposited() view returns (uint256)",
  "function outstanding() view returns (uint256)",
  "function seasonEnd() view returns (uint64)",
  "function fingerprintPaid(bytes32 fingerprint) view returns (bool)",
  "function withdrawable(address who) view returns (uint256)",
  "function release(bytes32 triggerId)",
  "function withdraw()",
];

const STATES = ["none", "proposed", "challenged", "finalized", "rejected"];
const REASONS = {
  1: "No one challenged it",
  2: "A challenge was upheld by the referee",
  3: "The referee stayed silent, so the claim stood",
};

const REFUSALS = {
  NotChallengeable: "This claim cannot be challenged now. It needs both signatures and an open window.",
  ChallengeWindowClosed: "The 24-hour challenge window has closed.",
  WrongStake: "The stake must be exactly 0.01 ETH.",
  ChallengeWindowOpen: "The challenge window is still open, so the claim cannot be finalized yet.",
  NotReady: "This claim is not ready to finalize.",
  NotFinalized: "The claim is not finalized, so the escrow will not pay it.",
  AlreadyPaid: "This claim has already been paid. The escrow pays each claim once.",
  NothingToWithdraw: "This address has nothing to withdraw.",
  NotResolver: "Only the referee key can do this.",
  NoChallenge: "There is no open challenge on this claim.",
  ResolveWindowOver: "The referee's 48-hour window is over. Anyone can now call expire.",
  ResolveWindowOpen: "The referee still has time to decide.",
  InsufficientPool: "The pool does not hold enough to pay this claim.",
  NoBeneficiary: "No beneficiary was committed for this place.",
  FingerprintMismatch: "The claim does not match its place and week.",
  PolicyOpen: "The payout table has not been committed yet.",
};

function readers() {
  return CHAIN.rpcs.map(
    (url) =>
      new JsonRpcProvider(url, CHAIN.chainId, {
        staticNetwork: Network.from(CHAIN.chainId),
        batchMaxCount: 1,
      }),
  );
}

export async function readWithFallback(job) {
  let last;
  for (const provider of readers()) {
    try {
      return await job(provider);
    } catch (err) {
      last = err;
    }
  }
  throw last;
}

async function loadClaim(provider, id) {
  const trigger = new Contract(CHAIN.trigger, TRIGGER_ABI, provider);
  const t = await trigger.getTrigger(id);
  const claim = {
    id,
    state: Number(t.state),
    windowStart: Number(t.windowStart),
    resolveDeadline: Number(t.resolveDeadline),
    challenger: t.challenger,
    stakeEth: formatEther(t.challengerStake),
    radarSigned: t.radarSigned,
    corroborators: Number(t.corroboratorCount),
    reason: Number(t.finalizationReason),
    signers: [],
  };
  if (claim.state !== 0) {
    const who = await trigger.signersOf(id);
    for (const address of who) {
      const role =
        address.toLowerCase() === CHAIN.roles.radar.toLowerCase()
          ? "Radar"
          : address.toLowerCase() === CHAIN.roles.rainfall.toLowerCase()
            ? "Rainfall"
            : "Signer";
      claim.signers.push({
        role,
        address,
        evidence: await trigger.evidenceOf(id, address),
      });
    }
  }
  return claim;
}

export async function readLive(slug) {
  const zone = CHAIN.zones[slug];
  if (!zone) return null;
  return readWithFallback(async (provider) => {
    const block = await provider.getBlock("latest");
    const escrow = new Contract(CHAIN.escrow, ESCROW_ABI, provider);
    const claim = await loadClaim(provider, zone.claimId);
    const paid = await escrow.fingerprintPaid(zone.claimId);
    return {
      block: block.number,
      now: block.timestamp,
      readAt: Date.now(),
      claim,
      paid,
    };
  });
}

export async function readEscrow() {
  return readWithFallback(async (provider) => {
    const escrow = new Contract(CHAIN.escrow, ESCROW_ABI, provider);
    const [balance, deposited, outstanding, locked, seasonEnd] = await Promise.all([
      provider.getBalance(CHAIN.escrow),
      escrow.deposited(),
      escrow.outstanding(),
      escrow.policyLocked(),
      escrow.seasonEnd(),
    ]);
    return {
      balanceEth: formatEther(balance),
      depositedEth: formatEther(deposited),
      outstandingEth: formatEther(outstanding),
      locked,
      seasonEnd: Number(seasonEnd),
    };
  });
}

export function describe(claim, now, paid) {
  const W = CHAIN.challengeWindow;
  const d = { key: STATES[claim.state] || "none", label: "", detail: "", until: 0, untilLabel: "", can: {} };
  if (claim.state === 0) {
    d.label = "No claim opened";
    d.detail = "Nobody has signed this place and week.";
  } else if (claim.state === 1) {
    if (!claim.windowStart) {
      d.key = "waiting";
      d.label = "Waiting for a second signature";
      d.detail = "One source has signed. A claim opens only when both have signed.";
    } else if (now < claim.windowStart + W) {
      d.key = "open";
      d.label = "Open for challenge";
      d.detail = "Both required sources signed. Anyone can stake 0.01 ETH against it until the window closes.";
      d.until = claim.windowStart + W;
      d.untilLabel = "Challenge window closes";
      d.can.challenge = true;
    } else {
      d.key = "ready";
      d.label = "Window closed, ready to finalize";
      d.detail = "Nobody challenged in time. Anyone can now finalize it.";
      d.can.finalize = true;
    }
  } else if (claim.state === 2) {
    if (now < claim.resolveDeadline) {
      d.key = "challenged";
      d.label = "Challenged, referee deciding";
      d.detail = "The claim is frozen. The referee can uphold or reject it until the deadline.";
      d.until = claim.resolveDeadline;
      d.untilLabel = "Referee deadline";
      d.can.resolve = true;
    } else {
      d.key = "expirable";
      d.label = "Referee silent, claim can stand";
      d.detail = "The referee's 48 hours are over. Anyone can call expire and the claim finalizes.";
      d.can.expire = true;
    }
  } else if (claim.state === 3) {
    d.label = paid ? "Finalized and paid" : "Finalized";
    d.detail = `${REASONS[claim.reason] || "Finalized."}${paid ? " The escrow has paid it once." : " The escrow has not paid it yet."}`;
    d.can.release = !paid;
  } else if (claim.state === 4) {
    d.label = "Rejected";
    d.detail = "The referee rejected it. It pays nothing.";
  }
  return d;
}

export function explorer(kind, value) {
  return `${CHAIN.explorer}/${kind}/${value}`;
}

export function shortAddr(addr) {
  return addr ? `${addr.slice(0, 6)}…${addr.slice(-4)}` : "";
}

export function friendlyError(err) {
  if (!err) return "Something went wrong.";
  if (err.code === "ACTION_REJECTED" || err.code === 4001) return "You declined in your wallet. Nothing was sent.";
  const name = err.revert?.name;
  if (name && REFUSALS[name]) return REFUSALS[name];
  if (err.info?.error?.code === 4001) return "You declined in your wallet. Nothing was sent.";
  return String(err.shortMessage || err.message || "Something went wrong.").slice(0, 240);
}

export function sandboxRecord(paid, slug) {
  if (!paid) {
    return {
      label: "SANDBOX",
      line: "No release yet. If one happens, the record is labelled SANDBOX. No Daraja call. No shillings moved.",
    };
  }
  const zone = CHAIN.zones[slug];
  return {
    label: "SANDBOX",
    line: `A release was copied for ${zone?.name || slug}. Rail: daraja-sandbox. moved_kes: false. This is a labelled record, not a phone payment.`,
  };
}

const wallet = { account: null, signer: null, chainOk: false };

export function walletState() {
  return { ...wallet, hasEthereum: typeof window !== "undefined" && Boolean(window.ethereum) };
}

async function ensureSepolia() {
  const hex = `0x${CHAIN.chainId.toString(16)}`;
  try {
    await window.ethereum.request({ method: "wallet_switchEthereumChain", params: [{ chainId: hex }] });
  } catch (err) {
    if (err && err.code === 4902) {
      await window.ethereum.request({
        method: "wallet_addEthereumChain",
        params: [
          {
            chainId: hex,
            chainName: "Sepolia",
            nativeCurrency: { name: "Sepolia Ether", symbol: "ETH", decimals: 18 },
            rpcUrls: [CHAIN.rpcs[0]],
            blockExplorerUrls: [CHAIN.explorer],
          },
        ],
      });
    } else {
      throw err;
    }
  }
}

export async function connectWallet() {
  if (!window.ethereum) throw new Error("No browser wallet found. Reading still works.");
  const provider = new BrowserProvider(window.ethereum);
  await provider.send("eth_requestAccounts", []);
  await ensureSepolia();
  wallet.signer = await provider.getSigner();
  wallet.account = await wallet.signer.getAddress();
  const net = await provider.getNetwork();
  wallet.chainOk = Number(net.chainId) === CHAIN.chainId;
  return walletState();
}

export async function sendAction(kind, slug) {
  const zone = CHAIN.zones[slug];
  if (!zone) throw new Error("This place has no claim on the testnet.");
  if (!wallet.signer) await connectWallet();
  if (!wallet.chainOk) {
    await ensureSepolia();
    await connectWallet();
  }
  const trigger = new Contract(CHAIN.trigger, TRIGGER_ABI, wallet.signer);
  const escrow = new Contract(CHAIN.escrow, ESCROW_ABI, wallet.signer);
  const id = zone.claimId;
  let call;
  let args = [];
  let overrides = {};
  if (kind === "challenge") {
    call = trigger.challenge;
    args = [id];
    overrides = { value: parseEther(CHAIN.stakeEth) };
  } else if (kind === "finalize") {
    call = trigger.finalize;
    args = [id];
  } else if (kind === "expire") {
    call = trigger.expire;
    args = [id];
  } else if (kind === "uphold") {
    call = trigger.resolve;
    args = [id, true];
  } else if (kind === "reject") {
    call = trigger.resolve;
    args = [id, false];
  } else if (kind === "release") {
    call = escrow.release;
    args = [id];
  } else if (kind === "withdraw-trigger") {
    call = trigger.withdraw;
  } else if (kind === "withdraw-escrow") {
    call = escrow.withdraw;
  } else {
    throw new Error("Unknown action.");
  }
  await call.staticCall(...args, overrides);
  const tx = await call(...args, overrides);
  await tx.wait();
  return tx.hash;
}
