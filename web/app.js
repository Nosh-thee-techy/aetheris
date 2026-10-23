/*
  Aetheris, live layer.

  What this file does
    1. Reads the FloodTrigger and PayoutEscrow contracts on Sepolia and fills in
       the places the HTML marks with data-live-* attributes.
    2. Recomputes, in the visitor's browser, the hashes the contracts hold, so
       a reader can check the record instead of trusting it.
    3. Lets a visitor with a wallet challenge, finalize, release or withdraw.

  What it will not do
    - It never invents chain state. If the chain cannot be read it says so and
      leaves the snapshot taken at deploy time, labelled as a snapshot.
    - It holds no keys. Every write goes through the visitor's own wallet.
    - It loads nothing from the network except JSON-RPC calls to the public
      Sepolia endpoints listed in chain-config.js.

  Time: all deadlines are judged against the latest block's timestamp, not the
  visitor's clock, because that is what the contract uses.
*/
(function () {
  "use strict";

  var C = window.AETHERIS;
  var E = window.ethers;
  var body = document.body;
  var page = body.getAttribute("data-page");

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function short(a) { return a ? a.slice(0, 6) + "…" + a.slice(-4) : ""; }
  function utc(ts) { return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 16) + " UTC"; }
  function link(href, text, mono) {
    var a = el("a", null, text);
    a.href = href;
    a.rel = "noopener";
    if (mono) a.className = "mono";
    return a;
  }
  function explorer(kind, value) { return C.explorer + "/" + kind + "/" + value; }

  if (!C || !C.trigger) { markUnavailable("The contracts are not deployed yet, so there is nothing to read."); return; }
  if (!E) { markUnavailable("The bundled chain library did not load, so live state is off. The snapshot below was taken at deploy time."); return; }

  /* ------------------------------------------------------------------ ABIs */

  var TRIGGER_ABI = [
    "function getTrigger(bytes32 id) view returns (tuple(bytes32 zoneId, bytes32 eventWeek, uint64 windowStart, uint64 resolveDeadline, uint8 state, address challenger, uint256 challengerStake, bool radarSigned, uint8 corroboratorCount, uint8 finalizationReason))",
    "function signersOf(bytes32 id) view returns (address[])",
    "function evidenceOf(bytes32 id, address who) view returns (bytes32)",
    "function withdrawable(address who) view returns (uint256)",
    "function ruleId() view returns (bytes32)",
    "function thresholdsHash() view returns (bytes32)",
    "function computeId(bytes32 zoneId, bytes32 eventWeek) view returns (bytes32)",
    "function challenge(bytes32 id) payable",
    "function finalize(bytes32 id)",
    "function expire(bytes32 id)",
    "function resolve(bytes32 id, bool upheld)",
    "function withdraw()",
    "event Attested(bytes32 indexed id, address indexed attester, bytes32 evidenceHash, bool radar)",
    "event WindowOpened(bytes32 indexed id, uint64 windowStart)",
    "event Challenged(bytes32 indexed id, address indexed challenger)",
    "event Finalized(bytes32 indexed id, uint8 reason)",
    "event Rejected(bytes32 indexed id, address indexed challenger)",
    "error NotAttester()", "error AlreadySigned()", "error Closed()", "error BondRequired()",
    "error NotChallengeable()", "error ChallengeWindowClosed()", "error WrongStake()",
    "error NotResolver()", "error NoChallenge()", "error ResolveWindowOver()", "error ResolveWindowOpen()",
    "error NotReady()", "error ChallengeWindowOpen()", "error NothingToWithdraw()", "error TransferFailed()"
  ];

  var ESCROW_ABI = [
    "function policyLocked() view returns (bool)",
    "function policyHash() view returns (bytes32)",
    "function deposited() view returns (uint256)",
    "function outstanding() view returns (uint256)",
    "function seasonEnd() view returns (uint64)",
    "function funder() view returns (address)",
    "function fingerprintPaid(bytes32 fingerprint) view returns (bool)",
    "function withdrawable(address who) view returns (uint256)",
    "function grantsOf(bytes32 zoneId) view returns (tuple(address beneficiary, uint256 amount)[])",
    "function release(bytes32 triggerId)",
    "function withdraw()",
    "event Released(bytes32 indexed triggerId, bytes32 indexed fingerprint, uint256 amount)",
    "error PolicyOpen()", "error NotFinalized()", "error AlreadyPaid()", "error FingerprintMismatch()",
    "error NoBeneficiary()", "error InsufficientPool()", "error NothingToWithdraw()", "error TransferFailed()"
  ];

  /* Plain-language reasons for refusals, so a visitor never sees raw selectors. */
  var REFUSALS = {
    NotChallengeable: "This claim cannot be challenged now. It needs both signatures and an open window.",
    ChallengeWindowClosed: "The 24-hour challenge window has closed.",
    WrongStake: "The stake must be exactly 0.01 ETH.",
    ChallengeWindowOpen: "The challenge window is still open, so the claim cannot be finalized yet.",
    NotReady: "This claim is not ready to finalize. It needs both signatures and no open challenge.",
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
    PolicyOpen: "The payout table has not been committed yet."
  };

  /* --------------------------------------------------------------- reading */

  var providers = C.rpcs.map(function (url) {
    return new E.JsonRpcProvider(url, C.chainId, { staticNetwork: E.Network.from(C.chainId), batchMaxCount: 1 });
  });

  /* Try each public endpoint in turn; give up only when all of them fail. */
  async function read(job) {
    var last;
    for (var i = 0; i < providers.length; i++) {
      try { return await job(providers[i]); } catch (err) { last = err; }
    }
    throw last;
  }

  var ZONES = C.zones;
  var STATES = ["none", "proposed", "challenged", "finalized", "rejected"];
  var REASONS = { 1: "No one challenged it", 2: "A challenge was upheld by the referee", 3: "The referee stayed silent, so the claim stood" };

  async function loadClaim(provider, id) {
    var trigger = new E.Contract(C.trigger.address, TRIGGER_ABI, provider);
    var t = await trigger.getTrigger(id);
    var claim = {
      id: id,
      state: Number(t.state),
      windowStart: Number(t.windowStart),
      resolveDeadline: Number(t.resolveDeadline),
      challenger: t.challenger,
      stake: t.challengerStake,
      radarSigned: t.radarSigned,
      corroborators: Number(t.corroboratorCount),
      reason: Number(t.finalizationReason),
      signers: []
    };
    if (claim.state !== 0) {
      var who = await trigger.signersOf(id);
      for (var i = 0; i < who.length; i++) {
        claim.signers.push({ address: who[i], evidence: await trigger.evidenceOf(id, who[i]), radar: who[i].toLowerCase() === C.roles.radar.toLowerCase() });
      }
    }
    return claim;
  }

  /* Everything the pages need in one pass, from one endpoint, at one block. */
  async function loadAll() {
    return read(async function (provider) {
      var block = await provider.getBlock("latest");
      var slugs = Object.keys(ZONES);
      var claims = await Promise.all(slugs.map(function (slug) { return loadClaim(provider, ZONES[slug].claimId); }));
      var escrow = new E.Contract(C.escrow.address, ESCROW_ABI, provider);
      var paid = await Promise.all(slugs.map(function (slug) { return escrow.fingerprintPaid(ZONES[slug].claimId); }));
      var out = { block: block.number, now: block.timestamp, readAt: Date.now(), zones: {} };
      slugs.forEach(function (slug, i) { out.zones[slug] = { claim: claims[i], paid: paid[i] }; });
      return out;
    });
  }

  /* ------------------------------------------------------ what a state means */

  /* One place that turns a stored claim into words, a marker shape and the
     next thing that can happen. Every page uses it, so they cannot disagree. */
  function describe(claim, now, paid) {
    var W = C.constants.challengeWindow;
    var d = { key: STATES[claim.state], dot: "no", label: "", detail: "", until: 0, untilLabel: "" };
    if (claim.state === 0) {
      d.label = "No claim opened";
      d.detail = "Nobody has signed this place and week.";
    } else if (claim.state === 1) {
      d.dot = "half";
      if (!claim.windowStart) {
        d.key = "waiting";
        d.label = "Waiting for a second signature";
        d.detail = "One source has signed. A claim opens only when radar and a second source have both signed.";
      } else if (now < claim.windowStart + W) {
        d.key = "open";
        d.label = "Open for challenge";
        d.detail = "Both required sources signed. Anyone can stake 0.01 ETH against it until the window closes.";
        d.until = claim.windowStart + W;
        d.untilLabel = "Challenge window closes in";
      } else {
        d.key = "ready";
        d.label = "Window closed, ready to finalize";
        d.detail = "Nobody challenged in time. Anyone can now finalize it.";
      }
    } else if (claim.state === 2) {
      d.dot = "half";
      if (now < claim.resolveDeadline) {
        d.key = "challenged";
        d.label = "Challenged, referee deciding";
        d.detail = "The claim is frozen. The referee can uphold or reject it until the deadline.";
        d.until = claim.resolveDeadline;
        d.untilLabel = "Referee deadline in";
      } else {
        d.key = "expirable";
        d.label = "Referee silent, claim can stand";
        d.detail = "The referee's 48 hours are over. Anyone can call expire and the claim finalizes.";
      }
    } else if (claim.state === 3) {
      d.dot = "signed";
      d.label = paid ? "Finalized and paid" : "Finalized";
      d.detail = (REASONS[claim.reason] || "Finalized.") + (paid ? ". The escrow has paid it once." : ". The escrow has not paid it yet.");
    } else if (claim.state === 4) {
      d.dot = "no";
      d.label = "Rejected";
      d.detail = "The referee rejected it. The challenger received the stake and both bonds. It pays nothing.";
    }
    return d;
  }

  function marker(kind) { return el("span", "dot " + kind); }

  function chip(d) {
    var node = el("span", "chip " + d.key);
    node.appendChild(marker(d.dot));
    node.appendChild(document.createTextNode(d.label));
    return node;
  }

  /* ----------------------------------------------------------- clock helpers */

  var clockOffset = 0; // chain time minus browser time, in seconds
  function chainNow() { return Math.floor(Date.now() / 1000) + clockOffset; }

  function tickCountdowns() {
    $all("[data-until]").forEach(function (node) {
      var end = Number(node.getAttribute("data-until"));
      if (!end) return;
      var left = end - chainNow();
      if (left <= 0) { node.textContent = "now"; return; }
      var h = Math.floor(left / 3600), m = Math.floor((left % 3600) / 60), s = left % 60;
      node.textContent = h + "h " + String(m).padStart(2, "0") + "m " + String(s).padStart(2, "0") + "s";
    });
  }
  setInterval(tickCountdowns, 1000);

  /* ------------------------------------------------------ status line + data */

  var latest = null;

  function setStatus(ok, text) {
    $all("[data-live-status]").forEach(function (node) {
      node.className = "live-status " + (ok ? "ok" : "bad");
      node.textContent = text;
    });
  }

  function markUnavailable(text) {
    $all("[data-live-status]").forEach(function (node) {
      node.className = "live-status bad";
      node.textContent = text;
    });
  }

  async function refresh() {
    try {
      latest = await loadAll();
      clockOffset = latest.now - Math.floor(latest.readAt / 1000);
      setStatus(true, "Live from Sepolia · block " + latest.block.toLocaleString("en-US") + " · read " + new Date(latest.readAt).toLocaleTimeString());
      render();
    } catch (err) {
      setStatus(false, "Could not reach the Sepolia RPC. Showing the snapshot taken at deploy time (block " + C.snapshot.block.toLocaleString("en-US") + "). " + (err && err.shortMessage ? err.shortMessage : ""));
    }
  }

  function render() {
    if (page === "claims") renderClaims();
    if (page === "claim") renderClaimPage();
    if (page === "payouts") renderPayouts();
    tickCountdowns();
    updateWalletUi();
  }

  /* --------------------------------------------------------------- claims list */

  function renderClaims() {
    var counts = { none: 0, waiting: 0, open: 0, ready: 0, challenged: 0, expirable: 0, finalized: 0, rejected: 0 };
    Object.keys(latest.zones).forEach(function (slug) {
      var z = latest.zones[slug];
      var d = describe(z.claim, latest.now, z.paid);
      counts[d.key] += 1;
      var cell = $('[data-live-zone="' + slug + '"]');
      if (!cell) return;
      clear(cell);
      cell.appendChild(chip(d));
      if (d.until) {
        var t = el("span", "until");
        t.appendChild(document.createTextNode(d.untilLabel + " "));
        var c = el("b"); c.setAttribute("data-until", d.until); t.appendChild(c);
        cell.appendChild(t);
      }
    });
    var tally = $("[data-live-tally]");
    if (tally) {
      var open = counts.open + counts.waiting + counts.ready + counts.challenged + counts.expirable;
      tally.textContent = (open + counts.finalized + counts.rejected) + " of " + Object.keys(latest.zones).length +
        " places have a claim on the testnet: " + open + " in progress, " + counts.finalized + " finalized, " + counts.rejected + " rejected.";
    }
  }

  /* ------------------------------------------------------------ claim detail */

  var slug = body.getAttribute("data-zone");
  var timelineLoaded = false;

  function renderClaimPage() {
    var z = latest.zones[slug];
    if (!z) return;
    var d = describe(z.claim, latest.now, z.paid);
    var stage = $("[data-live-stage]");
    if (stage) {
      clear(stage);
      stage.className = "stage " + d.key;
      var head = el("div", "stage-head");
      head.appendChild(chip(d));
      stage.appendChild(head);
      stage.appendChild(el("p", "stage-detail", d.detail));
      if (d.until) {
        var big = el("div", "countdown");
        big.setAttribute("data-until", d.until);
        stage.appendChild(big);
        stage.appendChild(el("p", "note", d.untilLabel + " (judged by the chain's clock, closes " + utc(d.until) + ")."));
      }
    }
    renderSignatures(z.claim);
    renderActions(z, d);
    if (!timelineLoaded) { timelineLoaded = true; loadTimeline(z.claim); }
  }

  /* On-chain signature rows, with the hash recomputed here and compared. */
  function renderSignatures(claim) {
    var host = $("[data-live-signatures]");
    if (!host) return;
    clear(host);
    var rows = [
      { label: "Radar attester", address: C.roles.radar, text: C.evidence.radarText },
      { label: "Rainfall attester", address: C.roles.rainfall, text: C.evidence.rainText }
    ];
    rows.forEach(function (r) {
      var signed = claim.signers.filter(function (s) { return s.address.toLowerCase() === r.address.toLowerCase(); })[0];
      var row = el("div", "sigrow");
      var top = el("div", "sig-top");
      top.appendChild(marker(signed ? "signed" : "no"));
      top.appendChild(el("b", null, r.label));
      top.appendChild(el("span", "sig-state", signed ? "signed" : "has not signed"));
      row.appendChild(top);
      var dl = el("dl");
      dl.appendChild(el("dt", null, "Address"));
      var dd = el("dd"); dd.appendChild(link(explorer("address", r.address), r.address, true)); dl.appendChild(dd);
      if (signed) {
        var mine = E.keccak256(E.toUtf8Bytes(r.text));
        var same = mine.toLowerCase() === signed.evidence.toLowerCase();
        dl.appendChild(el("dt", null, "Evidence hash on chain"));
        dl.appendChild(el("dd", "mono", signed.evidence));
        dl.appendChild(el("dt", null, "Hash of the text"));
        var dd2 = el("dd"); dd2.appendChild(el("code", null, r.text)); dl.appendChild(dd2);
        dl.appendChild(el("dt", null, "Recomputed here"));
        var verdict = el("dd", same ? "check ok" : "check bad", same ? "Matches. The signature names exactly this evidence." : "Does not match. Do not trust this signature.");
        dl.appendChild(verdict);
      }
      row.appendChild(dl);
      host.appendChild(row);
    });
  }

  /* ----------------------------------------------------------------- actions */

  function availability(z, now) {
    var c = z.claim, W = C.constants.challengeWindow, acct = wallet.account && wallet.account.toLowerCase();
    var a = {};
    // challenge
    if (c.state === 1 && c.windowStart && now < c.windowStart + W) a.challenge = { ok: true };
    else if (c.state === 0) a.challenge = { ok: false, why: "Nothing to challenge: no claim was opened here." };
    else if (c.state === 1 && !c.windowStart) a.challenge = { ok: false, why: "Not open yet: it needs a second signature first." };
    else if (c.state === 1) a.challenge = { ok: false, why: "The challenge window has closed." };
    else if (c.state === 2) a.challenge = { ok: false, why: "Already challenged." };
    else a.challenge = { ok: false, why: "This claim is already decided." };
    // finalize
    if (c.state === 1 && c.windowStart && now >= c.windowStart + W) a.finalize = { ok: true };
    else if (c.state === 1 && c.windowStart) a.finalize = { ok: false, why: "Not yet. The window closes " + utc(c.windowStart + W) + "." };
    else a.finalize = { ok: false, why: c.state === 3 ? "Already finalized." : "Only a claim with both signatures and no challenge can finalize." };
    // referee
    if (c.state === 2 && now < c.resolveDeadline) {
      a.resolve = acct === C.roles.resolver.toLowerCase() ? { ok: true } : { ok: false, why: "Only the referee key can decide. In this demo that is one key." };
    } else a.resolve = { ok: false, why: c.state === 2 ? "The referee's deadline passed. Use expire." : "There is no open challenge." };
    // expire
    a.expire = c.state === 2 && now >= c.resolveDeadline ? { ok: true } : { ok: false, why: c.state === 2 ? "The referee still has until " + utc(c.resolveDeadline) + "." : "There is no challenge waiting on the referee." };
    // release
    if (c.state === 3 && !z.paid) a.release = { ok: true };
    else if (z.paid) a.release = { ok: false, why: "Already paid once. The escrow will not pay it again." };
    else a.release = { ok: false, why: "The escrow pays only a finalized claim." };
    return a;
  }

  var ACTIONS = [
    { key: "challenge", title: "Challenge this claim", who: "Anyone with a wallet", note: "Stake 0.01 test ETH. The claim freezes and the referee has 48 hours. If it is rejected you receive your stake and both attesters' bonds. If it is upheld your stake goes to the slash pool. If the referee stays silent the claim stands and your stake comes back.", cta: "Stake 0.01 ETH and challenge" },
    { key: "finalize", title: "Finalize", who: "Anyone", note: "After the window closes with no challenge, this locks the claim in and returns both attesters' bonds to their withdrawable balance.", cta: "Finalize" },
    { key: "resolve", title: "Referee decision", who: "The referee key only", note: "Uphold finalizes the claim. Reject slashes both bonds to the challenger. No other outcome exists.", cta: "uphold" },
    { key: "expire", title: "Expire a silent referee", who: "Anyone", note: "If the referee does not decide within 48 hours, the claim stands and the challenger's stake is returned.", cta: "Expire" },
    { key: "release", title: "Release the payout", who: "Anyone", note: "Credits the beneficiaries committed before the season, once. The beneficiaries then withdraw. In this deployment they are placeholder addresses nobody holds a key for.", cta: "Release to beneficiaries" }
  ];

  function renderActions(z) {
    var host = $("[data-live-actions]");
    if (!host) return;
    var av = availability(z, latest.now);
    clear(host);
    ACTIONS.forEach(function (act) {
      var row = el("div", "act" + (av[act.key].ok ? " on" : ""));
      var text = el("div", "act-text");
      var h = el("h4"); h.appendChild(document.createTextNode(act.title + " ")); h.appendChild(el("span", "who-tag", act.who)); text.appendChild(h);
      text.appendChild(el("p", null, act.note));
      if (!av[act.key].ok) text.appendChild(el("p", "why-not", av[act.key].why));
      row.appendChild(text);
      var controls = el("div", "act-controls");
      if (act.key === "resolve") {
        ["uphold", "reject"].forEach(function (choice) {
          var b = el("button", "btn", choice === "uphold" ? "Uphold" : "Reject");
          b.type = "button"; b.disabled = !av.resolve.ok; b.setAttribute("data-do", "resolve:" + choice);
          controls.appendChild(b);
        });
      } else {
        var b = el("button", "btn" + (act.key === "challenge" ? " primary" : ""), act.cta);
        b.type = "button"; b.disabled = !av[act.key].ok; b.setAttribute("data-do", act.key);
        controls.appendChild(b);
      }
      row.appendChild(controls);
      host.appendChild(row);
    });
    $all("[data-do]", host).forEach(function (b) { b.addEventListener("click", function () { act(b.getAttribute("data-do")); }); });
  }

  /* --------------------------------------------------------------- timeline */

  async function loadTimeline(claim) {
    var host = $("[data-live-timeline]");
    if (!host) return;
    try {
      var events = await read(async function (provider) {
        var trigger = new E.Contract(C.trigger.address, TRIGGER_ABI, provider);
        var from = C.trigger.block;
        var id = claim.id;
        var sets = await Promise.all([
          trigger.queryFilter(trigger.filters.Attested(id), from),
          trigger.queryFilter(trigger.filters.WindowOpened(id), from),
          trigger.queryFilter(trigger.filters.Challenged(id), from),
          trigger.queryFilter(trigger.filters.Finalized(id), from),
          trigger.queryFilter(trigger.filters.Rejected(id), from),
          new E.Contract(C.escrow.address, ESCROW_ABI, provider).queryFilter(new E.Contract(C.escrow.address, ESCROW_ABI, provider).filters.Released(id), from)
        ]);
        var all = [].concat.apply([], sets);
        var stamps = {};
        for (var i = 0; i < all.length; i++) {
          if (!(all[i].blockNumber in stamps)) stamps[all[i].blockNumber] = (await provider.getBlock(all[i].blockNumber)).timestamp;
        }
        return all.map(function (log) { return { log: log, ts: stamps[log.blockNumber] }; })
          .sort(function (a, b) { return a.log.blockNumber - b.log.blockNumber || a.log.index - b.log.index; });
      });
      clear(host);
      if (!events.length) { host.appendChild(el("li", null, "No events on the testnet for this place and week.")); return; }
      events.forEach(function (e) {
        var name = e.log.fragment.name, args = e.log.args, text;
        if (name === "Attested") text = (args.radar ? "Radar" : "Rainfall") + " attester signed and posted a 0.01 ETH bond";
        else if (name === "WindowOpened") text = "Both required sources had signed. The 24-hour challenge window opened";
        else if (name === "Challenged") text = "Challenged by " + short(args.challenger) + " with a 0.01 ETH stake";
        else if (name === "Finalized") text = "Finalized. " + (REASONS[Number(args.reason)] || "");
        else if (name === "Rejected") text = "Rejected. The challenger received the stake and both bonds";
        else if (name === "Released") text = "The escrow released the payout to the committed beneficiaries";
        var li = el("li", "done");
        li.appendChild(el("span", "tl-when", utc(e.ts)));
        li.appendChild(el("span", null, text + " "));
        li.appendChild(link(explorer("tx", e.log.transactionHash), "tx " + short(e.log.transactionHash), true));
        host.appendChild(li);
      });
    } catch (err) {
      clear(host);
      host.appendChild(el("li", null, "The event history could not be read right now. The state above is still read directly from the contract."));
    }
  }

  /* ----------------------------------------------------------------- payouts */

  async function renderPayouts() {
    var host = $("[data-live-escrow]");
    try {
      var data = await read(async function (provider) {
        var escrow = new E.Contract(C.escrow.address, ESCROW_ABI, provider);
        var slugs = Object.keys(ZONES);
        var res = await Promise.all([
          provider.getBalance(C.escrow.address), escrow.deposited(), escrow.outstanding(), escrow.policyLocked(), escrow.policyHash(), escrow.seasonEnd(),
          Promise.all(slugs.map(function (s) { return escrow.grantsOf(ZONES[s].zoneId); })),
          escrow.queryFilter(escrow.filters.Released(), C.escrow.block)
        ]);
        return { balance: res[0], deposited: res[1], outstanding: res[2], locked: res[3], hash: res[4], seasonEnd: Number(res[5]), grants: res[6], released: res[7], slugs: slugs };
      });
      if (host) {
        clear(host);
        var dl = el("dl");
        function row(k, v) { dl.appendChild(el("dt", null, k)); var dd = el("dd"); if (typeof v === "string") dd.textContent = v; else dd.appendChild(v); dl.appendChild(dd); }
        row("Held by the escrow", E.formatEther(data.balance) + " test ETH");
        row("Deposited in total", E.formatEther(data.deposited) + " test ETH");
        row("Credited, not yet withdrawn", E.formatEther(data.outstanding) + " test ETH");
        row("Free to pay new claims", E.formatEther(data.balance - data.outstanding) + " test ETH");
        row("Payout table", data.locked ? "Committed, cannot change" : "Not committed yet");
        row("Policy hash", el("code", null, data.hash));
        row("Funder can reclaim unspent after", utc(data.seasonEnd));
        host.appendChild(dl);
      }
      var body2 = $("[data-live-grants]");
      if (body2) {
        clear(body2);
        data.slugs.forEach(function (s, i) {
          var grants = data.grants[i];
          var z = latest.zones[s];
          var d = describe(z.claim, latest.now, z.paid);
          grants.forEach(function (g) {
            var tr = el("tr");
            var th = el("th"); th.scope = "row"; th.appendChild(link(ZONES[s].page, ZONES[s].name)); tr.appendChild(th);
            var td1 = el("td"); td1.appendChild(link(explorer("address", g.beneficiary), short(g.beneficiary), true)); tr.appendChild(td1);
            tr.appendChild(el("td", "n", E.formatEther(g.amount) + " ETH"));
            var td3 = el("td"); td3.appendChild(chip(d)); tr.appendChild(td3);
            body2.appendChild(tr);
          });
        });
      }
      var rel = $("[data-live-released]");
      if (rel) {
        clear(rel);
        if (!data.released.length) rel.appendChild(el("li", null, "Nothing has been released yet. The escrow pays only a finalized claim, and only once."));
        data.released.forEach(function (log) {
          var li = el("li", "done");
          li.appendChild(document.createTextNode("Released " + E.formatEther(log.args.amount) + " ETH for claim " + short(log.args.triggerId) + " "));
          li.appendChild(link(explorer("tx", log.transactionHash), "tx " + short(log.transactionHash), true));
          rel.appendChild(li);
        });
      }
    } catch (err) {
      if (host) { clear(host); host.appendChild(el("p", "live-status bad", "The escrow could not be read right now. Try Refresh.")); }
    }
    renderWithdraw();
  }

  async function renderWithdraw() {
    var host = $("[data-live-withdraw]");
    if (!host) return;
    clear(host);
    if (!wallet.account) { host.appendChild(el("p", "note", "Connect a wallet to see whether this address has anything to withdraw: a returned bond, a returned stake, a slashed bond, or a payout.")); return; }
    try {
      var amounts = await read(async function (provider) {
        var t = new E.Contract(C.trigger.address, TRIGGER_ABI, provider);
        var e = new E.Contract(C.escrow.address, ESCROW_ABI, provider);
        return [await t.withdrawable(wallet.account), await e.withdrawable(wallet.account)];
      });
      [["trigger", "Bonds and stakes (FloodTrigger)", amounts[0]], ["escrow", "Payouts (PayoutEscrow)", amounts[1]]].forEach(function (r) {
        var line = el("div", "act" + (r[2] > 0n ? " on" : ""));
        var text = el("div", "act-text");
        text.appendChild(el("h4", null, r[1]));
        text.appendChild(el("p", null, short(wallet.account) + " can withdraw " + E.formatEther(r[2]) + " test ETH."));
        line.appendChild(text);
        var controls = el("div", "act-controls");
        var b = el("button", "btn", "Withdraw"); b.type = "button"; b.disabled = r[2] === 0n;
        b.addEventListener("click", function () { act("withdraw:" + r[0]); });
        controls.appendChild(b); line.appendChild(controls); host.appendChild(line);
      });
    } catch (err) { host.appendChild(el("p", "live-status bad", "Could not read this address's balances right now.")); }
  }

  /* ---------------------------------------------------------------- backtest */

  function bytesFromBase64(b64) {
    var bin = atob(b64), out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  function wireRuleCheck() {
    var button = $("[data-check-rule]");
    var out = $("[data-check-out]");
    if (!button || !out) return;
    button.disabled = false;
    button.addEventListener("click", async function () {
      clear(out);
      var fileHash = E.keccak256(bytesFromBase64(C.ruleYamlB64));
      var idHash = E.keccak256(E.toUtf8Bytes(C.ruleName));
      var onChain = null;
      try {
        onChain = await read(async function (provider) {
          var t = new E.Contract(C.trigger.address, TRIGGER_ABI, provider);
          return { thresholds: await t.thresholdsHash(), rule: await t.ruleId() };
        });
      } catch (err) { /* reported below */ }
      var dl = el("dl", "checks");
      function line(k, v, ok) {
        dl.appendChild(el("dt", null, k));
        var dd = el("dd"); dd.appendChild(el("code", null, v));
        if (ok !== undefined) dd.appendChild(el("span", ok ? "check ok" : "check bad", ok ? " matches" : " does not match"));
        dl.appendChild(dd);
      }
      line("Hash of config/rule.yaml, computed in your browser", fileHash);
      if (onChain) {
        line("thresholdsHash held by the contract", onChain.thresholds, onChain.thresholds.toLowerCase() === fileHash.toLowerCase());
        line("Hash of the rule name “" + C.ruleName + "”", idHash);
        line("ruleId held by the contract", onChain.rule, onChain.rule.toLowerCase() === idHash.toLowerCase());
      } else {
        out.appendChild(el("p", "live-status bad", "Could not read the contract right now, so only your browser's hash is shown."));
      }
      out.appendChild(dl);
    });
  }

  /* ------------------------------------------------------------------ wallet */

  var wallet = { account: null, provider: null, signer: null, chainOk: false };
  var SEPOLIA_HEX = "0x" + C.chainId.toString(16);

  function updateWalletUi() {
    var b = $("[data-wallet]");
    if (!b) return;
    b.hidden = false;
    if (!window.ethereum) { b.textContent = "No wallet found"; b.disabled = true; b.title = "Install a browser wallet such as MetaMask or Rabby to challenge or withdraw. Reading works without one."; return; }
    if (!wallet.account) { b.textContent = "Connect wallet"; b.disabled = false; return; }
    b.disabled = false;
    b.textContent = short(wallet.account) + (wallet.chainOk ? " · Sepolia" : " · wrong network");
  }

  async function connect() {
    if (!window.ethereum) return;
    wallet.provider = new E.BrowserProvider(window.ethereum);
    await wallet.provider.send("eth_requestAccounts", []);
    await ensureSepolia();
    wallet.signer = await wallet.provider.getSigner();
    wallet.account = await wallet.signer.getAddress();
    var net = await wallet.provider.getNetwork();
    wallet.chainOk = Number(net.chainId) === C.chainId;
    updateWalletUi();
    if (latest) render();
  }

  async function ensureSepolia() {
    try {
      await window.ethereum.request({ method: "wallet_switchEthereumChain", params: [{ chainId: SEPOLIA_HEX }] });
    } catch (err) {
      if (err && err.code === 4902) {
        await window.ethereum.request({ method: "wallet_addEthereumChain", params: [{ chainId: SEPOLIA_HEX, chainName: "Sepolia", nativeCurrency: { name: "Sepolia Ether", symbol: "ETH", decimals: 18 }, rpcUrls: [C.rpcs[0]], blockExplorerUrls: [C.explorer] }] });
      } else throw err;
    }
  }

  var walletButton = $("[data-wallet]");
  if (walletButton) walletButton.addEventListener("click", function () { connect().catch(function (e) { logTx("bad", friendly(e)); }); });
  if (window.ethereum && window.ethereum.on) {
    window.ethereum.on("accountsChanged", function (a) { wallet.account = a && a[0] ? a[0] : null; if (!wallet.account) { wallet.signer = null; } else { connect().catch(function () {}); } updateWalletUi(); if (latest) render(); });
    window.ethereum.on("chainChanged", function () { connect().catch(function () {}); });
  }
  updateWalletUi();

  /* ------------------------------------------------------------------ writes */

  function logTx(kind, text, href) {
    var host = $("[data-tx-log]");
    if (!host) return;
    host.hidden = false;
    host.className = "txlog " + kind;
    clear(host);
    host.appendChild(document.createTextNode(text + " "));
    if (href) host.appendChild(link(href, "view transaction"));
  }

  function friendly(err) {
    if (!err) return "Something went wrong.";
    if (err.code === "ACTION_REJECTED" || err.code === 4001) return "You declined in your wallet. Nothing was sent.";
    var name = err.revert && err.revert.name;
    if (name && REFUSALS[name]) return REFUSALS[name];
    if (err.info && err.info.error && err.info.error.code === 4001) return "You declined in your wallet. Nothing was sent.";
    return (err.shortMessage || err.message || "Something went wrong.").slice(0, 240);
  }

  async function act(what) {
    try {
      if (!wallet.signer) await connect();
      if (!wallet.chainOk) { await ensureSepolia(); await connect(); }
      var parts = what.split(":"), key = parts[0], arg = parts[1];
      var trigger = new E.Contract(C.trigger.address, TRIGGER_ABI, wallet.signer);
      var escrow = new E.Contract(C.escrow.address, ESCROW_ABI, wallet.signer);
      var id = slug ? ZONES[slug].claimId : null;
      var call, args = [], overrides = {};
      if (key === "challenge") {
        var ok = $("[data-confirm-challenge]");
        if (ok && !ok.checked) { logTx("bad", "Tick the box first to confirm you are staking 0.01 Sepolia test ETH."); return; }
        call = trigger.challenge; args = [id]; overrides = { value: E.parseEther("0.01") };
      } else if (key === "finalize") { call = trigger.finalize; args = [id]; }
      else if (key === "expire") { call = trigger.expire; args = [id]; }
      else if (key === "resolve") { call = trigger.resolve; args = [id, arg === "uphold"]; }
      else if (key === "release") { call = escrow.release; args = [id]; }
      else if (key === "withdraw") { call = (arg === "trigger" ? trigger : escrow).withdraw; }
      else return;

      logTx("wait", "Checking that the contract will accept this…");
      await call.staticCall.apply(call, args.concat([overrides])); // refusals surface here as plain sentences
      logTx("wait", "Confirm in your wallet…");
      var tx = await call.apply(null, args.concat([overrides]));
      logTx("wait", "Submitted. Waiting for it to be mined…", explorer("tx", tx.hash));
      await tx.wait();
      logTx("ok", "Confirmed.", explorer("tx", tx.hash));
      timelineLoaded = false;
      await refresh();
    } catch (err) {
      logTx("bad", friendly(err));
    }
  }

  /* -------------------------------------------------------------------- go */

  var refreshButton = $("[data-refresh]");
  if (refreshButton) refreshButton.addEventListener("click", function () { timelineLoaded = false; refresh(); });
  wireRuleCheck();
  if (page === "claims" || page === "claim" || page === "payouts") {
    refresh();
    setInterval(function () { if (!document.hidden) refresh(); }, 45000);
  }
  if (page === "payouts") renderWithdraw();
})();
