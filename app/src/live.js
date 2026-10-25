import {
  CHAIN,
  connectWallet,
  describe,
  explorer,
  friendlyError,
  readEscrow,
  readLive,
  sandboxRecord,
  sendAction,
  shortAddr,
  walletState,
} from "./chain.js";

function $(sel, root = document) {
  return root.querySelector(sel);
}

function setText(node, text, cls) {
  if (!node) return;
  node.textContent = text;
  if (cls) node.className = cls;
}

function utc(ts) {
  return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 16) + " UTC";
}

export function paintWalletButton() {
  const btn = $("[data-wallet]");
  if (!btn) return;
  const w = walletState();
  if (!w.hasEthereum) {
    btn.textContent = "No wallet";
    btn.disabled = true;
    btn.title = "Install a browser wallet to challenge or withdraw. Reading works without one.";
    return;
  }
  btn.disabled = false;
  if (!w.account) {
    btn.textContent = "Connect wallet";
    return;
  }
  btn.textContent = `${shortAddr(w.account)}${w.chainOk ? " · Sepolia" : " · wrong network"}`;
}

export function logTx(kind, text, href) {
  const host = $("[data-tx-log]");
  if (!host) return;
  host.hidden = false;
  host.className = `txlog ${kind}`;
  host.innerHTML = href
    ? `${text} <a href="${href}" rel="noopener">view transaction</a>`
    : text;
}

export async function refreshClaim(slug) {
  const status = $("[data-live-status]");
  const stage = $("[data-live-claim]");
  if (!status && !stage) return null;
  if (!CHAIN.zones[slug]) {
    setText(status, "No claim on the testnet for this place. Silence counts as no. Showing the deploy snapshot.", "live-status");
    return null;
  }
  setText(status, "Reading Sepolia…", "live-status");
  try {
    const live = await readLive(slug);
    const d = describe(live.claim, live.now, live.paid);
    setText(
      status,
      `Live from Sepolia · block ${live.block.toLocaleString("en-US")} · read ${new Date(live.readAt).toLocaleTimeString()}. If this line fails later, the snapshot below stays.`,
      "live-status ok",
    );
    if (stage) {
      const signers = (live.claim.signers || [])
        .map((s) => `<div><span class="k">${s.role}</span><code>${s.address}</code></div>`)
        .join("");
      stage.innerHTML = `
        <p><b>${d.label}</b></p>
        <p>${d.detail}</p>
        ${d.until ? `<p class="note">${d.untilLabel} ${utc(d.until)} (chain clock).</p>` : ""}
        <div class="grid">${signers}</div>
        <p class="note">Claim <code>${live.claim.id}</code></p>
        <div class="cta">
          ${d.can.challenge ? `<button type="button" class="btn" data-act="challenge" disabled>Challenge · 0.01 ETH</button>` : ""}
          ${d.can.finalize ? `<button type="button" class="btn primary" data-act="finalize">Finalize</button>` : ""}
          ${d.can.expire ? `<button type="button" class="btn primary" data-act="expire">Expire (referee silent)</button>` : ""}
          ${d.can.resolve ? `<button type="button" class="btn" data-act="uphold">Uphold</button><button type="button" class="btn" data-act="reject">Reject</button>` : ""}
          ${d.can.release ? `<button type="button" class="btn primary" data-act="release">Release from escrow</button>` : ""}
        </div>
        ${d.can.challenge ? `<label class="field"><input type="checkbox" data-confirm-challenge> I am staking 0.01 Sepolia test ETH against this claim.</label>` : ""}
      `;
    }
    const sand = $("[data-sandbox]");
    if (sand) {
      const rec = sandboxRecord(live.paid, slug);
      sand.innerHTML = `<b>${rec.label}.</b> ${rec.line}`;
    }
    return live;
  } catch (err) {
    setText(
      status,
      `Could not reach Sepolia. Showing the snapshot taken at deploy (block ${CHAIN.snapshotBlock.toLocaleString("en-US")}). ${friendlyError(err)}`,
      "live-status bad",
    );
    return null;
  }
}

export async function refreshEscrow() {
  const host = $("[data-live-escrow]");
  if (!host) return;
  host.innerHTML = `<p class="note">Reading the escrow…</p>`;
  try {
    const data = await readEscrow();
    host.innerHTML = `
      <div class="grid">
        <div><span class="k">Held now</span>${data.balanceEth} test ETH</div>
        <div><span class="k">Deposited</span>${data.depositedEth} test ETH</div>
        <div><span class="k">Credited, not withdrawn</span>${data.outstandingEth} test ETH</div>
        <div><span class="k">Payout table</span>${data.locked ? "Committed. Cannot change. No hand-release." : "Not committed yet"}</div>
        <div><span class="k">Funder reclaim after</span>${utc(data.seasonEnd)}</div>
      </div>
    `;
  } catch (err) {
    host.innerHTML = `<p class="live-status bad">The escrow could not be read. The snapshot on this page is still the deploy record. ${friendlyError(err)}</p>`;
  }
}

export async function afterPage(path) {
  paintWalletButton();
  if (path.startsWith("/claim/")) {
    await refreshClaim(path.slice("/claim/".length));
  }
  if (path === "/claims") {
    await refreshEscrow();
    await refreshClaim("kabonyo-kanyagwal");
  }
  if (path === "/desk/farmer") {
    try {
      const live = await readLive("kabonyo-kanyagwal");
      const sand = $("[data-sandbox]");
      if (sand && live) {
        const rec = sandboxRecord(live.paid, "kabonyo-kanyagwal");
        sand.innerHTML = `<b>${rec.label}.</b> ${rec.line}`;
      }
    } catch {
      const sand = $("[data-sandbox]");
      if (sand) sand.innerHTML = `<b>SANDBOX.</b> Could not read whether a release happened. This demo still sends no M-PESA.`;
    }
  }
}

export async function onWalletClick() {
  try {
    await connectWallet();
    paintWalletButton();
    logTx("ok", "Wallet connected on Sepolia. Reading still works if you disconnect.");
  } catch (err) {
    logTx("bad", friendlyError(err));
  }
}

export async function onAct(kind, slug) {
  if (kind === "challenge") {
    const box = $("[data-confirm-challenge]");
    if (box && !box.checked) {
      logTx("bad", "Tick the box first to confirm you are staking 0.01 Sepolia test ETH.");
      return;
    }
  }
  try {
    logTx("wait", "Checking that the contract will accept this…");
    const hash = await sendAction(kind, slug);
    logTx("ok", "Confirmed on Sepolia.", explorer("tx", hash));
    await refreshClaim(slug);
    if (document.querySelector("[data-live-escrow]")) await refreshEscrow();
  } catch (err) {
    logTx("bad", friendlyError(err));
  }
}
