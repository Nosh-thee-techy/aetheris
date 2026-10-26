const WORDS = ["none", "one", "two", "three", "four", "five", "six", "seven"];

const HTML_DESKS = {
  "/for-data.html": "/desk/data",
  "/for-insurer.html": "/desk/insurer",
  "/for-reinsurer.html": "/desk/reinsurer",
  "/for-responder.html": "/desk/responder",
  "/for-research.html": "/desk/research",
  "/for-farmer.html": "/desk/farmer",
  "/workspaces.html": "/desks",
  "/login.html": "/enter",
  "/index.html": "/",
};

export function normalizePath(path) {
  if (HTML_DESKS[path]) return HTML_DESKS[path];
  const claimFile = path.match(/^\/claim-([a-z0-9-]+)\.html$/);
  if (claimFile) return `/claim/${claimFile[1]}`;
  if (path === "/overview.html" || path === "/overview") return "/method";
  if (path === "/claims.html") return "/claims";
  if (path === "/backtest.html") return "/backtest";
  return path;
}

function word(n) {
  return WORDS[n] ?? String(n);
}

function pct(value) {
  if (value == null) return "—";
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function rainBar(cache) {
  const mm = cache?.rainfall?.mm ?? 0;
  const line = cache?.rainfall?.line_mm ?? 40;
  const scale = 80;
  return `
    <div class="gauge" role="img" aria-label="${mm} millimetres against a line at ${line} millimetres">
      <i class="rain" style="width:${Math.min(100, (mm / scale) * 100)}%"></i>
      <b style="left:${Math.min(100, (line / scale) * 100)}%"></b>
    </div>
    <div class="gauge-scale"><span>0 mm</span><span>line ${line} mm</span><span>${scale} mm</span></div>`;
}

function radarBar(place, cache) {
  if (place.radar === "abstain" || place.fraction == null) {
    return `<p class="note">No outline. Radar was not run here.</p>`;
  }
  const line = cache?.radar?.line ?? 0.05;
  return `
    <div class="gauge" role="img" aria-label="${pct(place.fraction)} open water against a line at ${pct(line)}">
      <i class="radar" style="width:${Math.min(100, place.fraction * 100)}%"></i>
      <b style="left:${Math.min(100, line * 100)}%"></b>
    </div>
    <p class="note">${pct(place.fraction)} of land pixels. Line ${pct(line)}.</p>`;
}

export function methodPage(ctx) {
  const { cache, esc, shell, weekLabel } = ctx;
  const places = cache.places || [];
  const n = places.length;
  const radarYes = cache.radar?.signed ?? 0;
  const radarNo = cache.radar?.below ?? 0;
  const unassessed = cache.radar?.no_geometry ?? 0;
  const rainYes = cache.rainfall?.signed ?? 0;
  const open = places.find((p) => p.both === "yes") || places[0];
  const frozen = cache.rule?.frozen_on || "";
  return shell("Method — Aetheris", `
    <section class="block"><div class="wrap">
      <p class="eyebrow">Verification layer · flood data · Kenya</p>
      <h1>Rain data said “flood” in ${word(n)} places. <em>Radar could confirm ${word(radarYes)}.</em></h1>
      <p class="lede">Flood payouts and alerts rest on satellite rainfall estimates that are sparse on the ground and often wrong in heavy rain. <strong>Aetheris checks them against Sentinel-1 radar</strong>, which sees whether land is actually under water, for each place and week, and records the result where anyone can check it or challenge it. This is the first week we checked: the Nyando basin, ${esc(weekLabel())}.</p>
      <div class="cta">
        <a class="btn primary" href="/enter">Enter a desk</a>
        <a class="btn" href="/claims">See the claims</a>
        ${open ? `<a class="btn" href="/claim/${esc(open.slug)}">Open the one live claim</a>` : ""}
        <a class="btn" href="/backtest">Read the backtest</a>
      </div>
      <ul class="stats">
        <li><div><p class="n">${n}</p><p>places that news reports said flooded</p></div></li>
        <li><div><p class="n rain">${rainYes}</p><p>where rainfall data signed “flood”</p></div></li>
        <li><div><p class="n radar">${radarYes}</p><p>where radar also signed, so a claim opened. ${radarNo} radar said no; ${unassessed} could not be assessed.</p></div></li>
      </ul>
    </div></section>
    <section class="block alt"><div class="wrap">
      <div class="sec-head"><span class="num">01</span><h2>When the data misses the flood, nobody can see why</h2></div>
      <p class="lede">Smallholder farmers and pastoralists in flood-prone basins are paid by weather-index insurance, or helped by alerts, only when the data says a flood happened. When that data misses their flood they get nothing, and the decision was made by a single operator, from an estimate, with no reason attached.</p>
      <p class="note">Aetheris attaches the reason. Each decision shows what each source measured, against which line, and who signed. It also counts how often the two sources miss a reported flood. That count is not “farmers are better off,” and we have not shown that anyone will use this. Today every payout in this demo is on a testnet or a sandbox.</p>
      <h3>What the research says</h3>
      <ul class="limits">
        <li><b>Ground stations are few.</b><span>Africa’s average density of stations meeting WMO standards is eight times below the recommended level, and as of October 2024 Chad was reporting 3% of the surface observations it is required to. <a href="https://eos.org/features/building-better-weather-networks">Eos</a></span></li>
        <li><b>Satellite rainfall is imperfect where it matters.</b><span>Against 596 TAHMO gauges, every product tested overestimated light rain and underestimated heavy rain (<a href="https://doi.org/10.1002/essoar.10509210.1">preprint</a>). In East Africa, CHIRPS had a 28% wet bias in daily rainfall (<a href="https://doi.org/10.1175/jhm-d-21-0161.1">published version</a>). Another study found CHIRPS missed 98% of the daily extreme-rain events its gauges recorded (<a href="https://doi.org/10.1175/jhm-d-21-0145.1">36 stations</a>). The studies differ on how good CHIRPS is, so read the numbers with care.</span></li>
        <li><b>Ground data is gated.</b><span>ICPAC receives station data from national met services under bilateral agreements, and each service sets its own terms, some with cost recovery. <a href="https://www.icpac.net/events/regional-data-managers-biannual-meeting-on-climate-data-sharing-framework/">ICPAC</a></span></li>
        <li><b>Index insurance already runs in Kenya on satellite triggers.</b><span>In 2021 Etherisc and ACRE Africa onboarded more than 17,000 smallholders and began paying some through M-Pesa. <a href="https://blog.etherisc.com/etherisc-update-etherisc-and-acre-africa-announce-first-payouts-through-blockchain-based-platform-a0c5194214f4">Etherisc</a> Those sources do not measure how often such triggers miss a real flood. That is what this project counts.</span></li>
      </ul>
      <p class="note"><b>What is new here, and what is not.</b> We found no published open-code method that cross-validates gauge readings against satellite products. We did not search specifically for radar-versus-rainfall cross-checks, which may exist in the flood-mapping literature, so we do not claim the cross-check itself is new. What we add is recording each disagreement as a signed, challengeable public claim tied to a payout rule.</p>
    </div></section>
    <section class="block"><div class="wrap">
      <div class="sec-head"><span class="num">02</span><h2>A flood is accepted only when radar and a second source both sign</h2></div>
      <p class="lede">Each place and week is one claim. Signing means “this payout rule fired”, not “I saw something”. Silence counts as no. Rainfall alone can never open a claim.</p>
      <ol class="steps">
        <li><b>Radar signs.</b> Sentinel-1 shows open water on enough of the place’s land, with permanent water removed. Required. Without it nothing opens.</li>
        <li><b>A second source signs.</b> Rain over the upstream catchment crosses the line. Each signer posts a 0.01 ETH bond and its own evidence hash.</li>
        <li><b>Anyone can challenge.</b> For 24 hours, anyone can stake 0.01 ETH against the claim. A challenge freezes it. The referee can only uphold or reject.</li>
        <li><b>It finalizes.</b> If no one challenged, or the referee stayed silent for 48 hours, the claim stands. Bonds come back. A rejected claim slashes the bonds to the challenger.</li>
        <li><b>It pays once.</b> Only a finalized claim releases funds, only to beneficiaries committed before the season, and each place-week-rule can be paid at most once.</li>
      </ol>
      <p class="note"><b>The rule is frozen.</b> Radar line: open water below −16 dB on at least 5.0% of land pixels. Rainfall line: 40 mm over three days on the upstream catchment. Fixed on ${esc(frozen)}, before this week was scored, and hashed into every claim id. These are untuned starting values, not fitted to this flood.</p>
    </div></section>
    <section class="block alt"><div class="wrap">
      <div class="sec-head"><span class="num">03</span><h2>Who this is for, and how we know</h2></div>
      <p class="lede">The direct user is the <b>trigger analyst at an insurer or aggregator</b>. The people most affected, smallholders and pastoralists, are the beneficiaries, not the users. We have not interviewed anyone. The last column says which rows rest on research and which are our assumption.</p>
      <table>
        <caption>Stakeholders, what each gains, and the basis for saying so</caption>
        <thead><tr><th>Who</th><th>Problem they face</th><th>What Aetheris gives them</th><th>Basis</th></tr></thead>
        <tbody>
          <tr><th>Insurers and aggregators</th><td>Triggers can miss real floods or fire without loss, and each dispute is costly to settle.</td><td>A trigger-design desk: what rainfall-only would pay, what this rule pays. <a href="/desk/insurer">Insurer desk</a></td><td><b>Researched in part.</b> Satellite-triggered index insurance runs in Kenya at scale. That triggers miss floods is our reading of the field.</td></tr>
          <tr><th>Reinsurers</th><td>They need a transparent event footprint they can put in their own model.</td><td>One named event, not a stochastic cat model. <a href="/desk/reinsurer">Event loss</a></td><td><b>Assumption.</b> We have not interviewed a reinsurer.</td></tr>
          <tr><th>Disaster responders and policymakers</th><td>Releasing funds or alerts on one forecast or one report is risky, and the decision has to be defended later.</td><td>A second instrument before a release, and a public record of the evidence. Not an official forecast. <a href="/desk/responder">Responder desk</a></td><td><b>Brief, not an interview.</b> <a href="https://www.anticipation-hub.org/Documents/Other/START_READY_-_2_pager.pdf">Start Ready</a> on timely, effective action. <a href="https://disasterlaw.ifrc.org/media/4430">IFRC, From Alert to Action</a> for policymakers and accountability. We have not interviewed a county officer.</td></tr>
          <tr><th>Data producers</th><td>Gauges are sparse, station data is gated, and users cannot tell which satellite product to trust.</td><td>A connected desk on CHIRPS and Sentinel-1. <a href="/desk/data">Data desk</a></td><td><b>Researched.</b> Station sparsity, data-sharing terms and rainfall bias are cited above.</td></tr>
          <tr><th>Researchers</th><td>Validation studies contradict each other, and gauge data is hard to get.</td><td>The open method, the counts, and the files. <a href="/desk/research">Research desk</a></td><td><b>Researched.</b> The CHIRPS studies cited above disagree.</td></tr>
          <tr><th>Smallholders and pastoralists</th><td>Unpaid when the index misses their flood, with no visible reason.</td><td>A page an insurer or responder can show: the reason for each decision, and a sandbox message if the demo releases a payout. <a href="/desk/farmer">Smallholder view</a></td><td><b>Assumption</b>, inferred from the basis-risk research. Not validated with users.</td></tr>
        </tbody>
      </table>
    </div></section>
    <section class="block"><div class="wrap">
      <div class="sec-head"><span class="num">04</span><h2>How it is built</h2></div>
      <ol class="steps">
        <li><b>Sources.</b> Sentinel-1 radar (RTC), CHIRPS rainfall, JRC permanent water. Read offline for one week.</li>
        <li><b>Frozen rule.</b> <code>config/rule.yaml</code>. Its hash is part of every claim id. Frozen, hash on the testnet.</li>
        <li><b>Offline week job.</b> Scene → radar CSV → rainfall rows → <code>python -m backtest.week</code>. The website reads those files. It does not download a GeoTIFF, and it does not run a RAG.</li>
        <li><b>FloodTrigger and PayoutEscrow.</b> Deployed on Sepolia. Unaudited. Beneficiaries are placeholders.</li>
        <li><b>M-PESA mirror.</b> A function that writes a record labelled SANDBOX. No Daraja call is made.</li>
      </ol>
      <p class="note">Not built: a committee or vote for the referee (one named key decides today), a ground-gauge attester, IMERG rainfall, live raster ingest on page load, and any check that real people want this. A second week is allowed only if the rule file is unchanged.</p>
    </div></section>
    <section class="block alt"><div class="wrap">
      <div class="sec-head"><span class="num">05</span><h2>What we are not claiming</h2></div>
      <ul class="limits">
        <li><b>Radar has blind spots.</b><span>It sees open water. It does not see flood under crops, trees or buildings, and Sentinel-1’s 2024 revisit is twelve days. Radar is the reference for this check, not ground truth.</span></li>
        <li><b>The sources overlap.</b><span>Rainfall and radar describe the same storm. Two signatures are not two independent witnesses.</span></li>
        <li><b>One season, seven news reports.</b><span>Counts here are indicative, not a validation study. Reports favour places that reporters and rescuers could reach. There are no “did not flood” labels yet.</span></li>
        <li><b>No gauges, and none stubbed.</b><span>There is no TAHMO or Kenya Met file in this repository. Do not invent stations.</span></li>
        <li><b>We do not prove use or impact.</b><span>The farmer page is a reason you can check: yes, no, or we could not look. It is not advice to plant, move, or ignore Kenya Met.</span></li>
        <li><b>Payouts are not real.</b><span>The escrow holds testnet ETH. M-PESA is a Daraja sandbox. The contracts are unaudited.</span></li>
      </ul>
    </div></section>
  `, "/method");
}

export function claimsPage(ctx) {
  const { cache, esc, shell, weekLabel } = ctx;
  const places = cache.places || [];
  const rain = cache.rainfall || {};
  const chain = cache.chain;
  const unassessed = cache.radar?.no_geometry ?? 0;
  const rows = places.map((p) => `
    <a class="card" href="/claim/${esc(p.slug)}">
      <div class="body">
        <span class="who">${esc(p.scale)}</span>
        <h3>${esc(p.name)}</h3>
        <p><span class="dot ${esc(p.marker)}"></span> ${esc(p.outcome)}</p>
        <p>Radar ${esc(p.radar)} · Rain ${esc(p.rain)} · ${esc(p.snapshot)}</p>
      </div>
    </a>`).join("");
  const explorer = chain?.explorer || "https://sepolia.etherscan.io";
  return shell("Claims — Aetheris", `
    <section class="block"><div class="wrap">
      <p class="eyebrow">Claims · Nyando basin · ${esc(weekLabel())}</p>
      <h1>Seven places, one flood week</h1>
      <p class="lede">News reports named these seven places as flooded. For each one, the rule asks radar and rainfall whether they sign. Where both do, a claim opens on the testnet. Rainfall alone never opens a claim.</p>
      <p class="note">${esc(chain?.note || "Snapshot at deploy. The page does not invent chain state.")} Nothing here moves real money. M-PESA is a labelled sandbox.</p>
      <p class="live-status" data-live-status>Live state is off until Sepolia answers. The snapshot stays if it does not.</p>
      <div class="sheet">
        <p><b>Rainfall, for every place at once.</b> It is read on the upstream headwaters, not on each place.</p>
        ${rainBar(cache)}
        <p><b>${esc(rain.mm)} mm</b> in the three days to 6 May (CHIRPS). Signed for all ${places.length} places.</p>
      </div>
      <div class="cards">${rows}</div>
      <p class="note">Boxes are working extents from OpenStreetMap, not surveyed flood outlines. ${unassessed} places were left unassessed rather than measured at the wrong location. The six places without a claim are not hidden failures: the rule did not fire there.</p>
    </div></section>
    <section class="block alt"><div class="wrap">
      <div class="sec-head"><span class="num">Escrow</span><h2>Payouts: the escrow</h2></div>
      <p class="lede">A contract holds testnet ETH and pays only a finalized claim, once, to a table fixed before any claim existed. The beneficiaries in this deployment are placeholders. Nobody holds a key for them.</p>
      ${chain ? `
        <div class="grid">
          <div><span class="k">PayoutEscrow</span><a href="${esc(explorer)}/address/${esc(chain.escrow.address)}"><code>${esc(chain.escrow.address)}</code></a></div>
          <div><span class="k">FloodTrigger</span><a href="${esc(explorer)}/address/${esc(chain.trigger.address)}"><code>${esc(chain.trigger.address)}</code></a></div>
          <div><span class="k">Funder</span><a href="${esc(explorer)}/address/${esc(chain.roles.funder)}"><code>${esc(chain.roles.funder)}</code></a></div>
          <div><span class="k">Pool at snapshot</span>${esc(chain.pool_balance_eth)} ETH</div>
        </div>
        <p class="note">Snapshot at ${esc(chain.snapshot_at)}. ${esc(chain.beneficiaries)}. No hand-release. Only a finalized claim, once.</p>
      ` : `<p class="note">Not deployed yet.</p>`}
      <div data-live-escrow></div>
      <div data-live-claim></div>
      <p class="txlog" data-tx-log hidden></p>
      <p class="note" data-sandbox><b>SANDBOX.</b> No Daraja call. No shillings moved.</p>
    </div></section>
  `, "/claims");
}

export function backtestPage(ctx) {
  const { cache, esc, shell } = ctx;
  const places = cache.places || [];
  const counts = cache.counts || { rules: {}, misses: {} };
  const radarYes = cache.radar?.signed ?? 0;
  const radarNo = cache.radar?.below ?? 0;
  const unassessed = cache.radar?.no_geometry ?? 0;
  const n = places.length;
  const both = places.filter((p) => p.radar === "yes" && p.rain === "yes");
  const rainOnly = places.filter((p) => p.radar === "no" && p.rain === "yes");
  const none = places.filter((p) => p.radar === "abstain" && p.rain === "yes");
  const rule = counts.rules?.radar_plus_rainfall || {};
  const names = (group) => group.map((p) => p.name).join(", ") || "0";
  const missRows = [
    ["Radar had no pass that week", counts.misses?.no_scene ?? 0],
    ["Radar saw too little open water", counts.misses?.below_threshold ?? 0],
    ["Radar signed, the second source did not", counts.misses?.uncorroborated ?? 0],
    ["Rainfall data was missing", counts.misses?.rainfall_gap ?? 0],
    ["No outline to measure, radar not run", counts.misses?.no_geometry ?? 0],
  ];
  const ruleRows = [
    ["Radar only", counts.rules?.radar_only],
    ["Radar and rainfall (the rule)", counts.rules?.radar_plus_rainfall],
    ["Rainfall only", counts.rules?.rainfall_only],
  ];
  return shell("Backtest — Aetheris", `
    <section class="block"><div class="wrap">
      <p class="eyebrow">Backtest · one season · counts only</p>
      <h1>Where the sources agreed, disagreed, and what was missed</h1>
      <p class="lede">One flood week, ${n} places, one frozen rule. We report counts, not an accuracy percentage, because seven news reports cannot carry one. The rule was fixed on ${esc(cache.rule?.frozen_on || "")}, before this week was scored, and we did not tune it afterwards.</p>
    </div></section>
    <section class="block alt"><div class="wrap">
      <div class="sec-head"><span class="num">01</span><h2>Agreement</h2></div>
      <table>
        <caption>Radar (rows) against rainfall (columns), ${n} places reported flooded</caption>
        <thead><tr><th></th><th>Rainfall signed</th><th>Rainfall did not sign</th></tr></thead>
        <tbody>
          <tr><th>Radar signed</th><td><b>${both.length}</b><br>${esc(names(both))}</td><td>0</td></tr>
          <tr><th>Radar did not sign</th><td><b>${rainOnly.length}</b><br>${esc(names(rainOnly))}</td><td>0</td></tr>
          <tr><th>Radar not assessed</th><td><b>${none.length}</b><br>${esc(names(none))}</td><td>0</td></tr>
        </tbody>
      </table>
      <table>
        <caption>Three rules on the same seven places</caption>
        <thead><tr><th></th><th>Found</th><th>Missed</th><th>False triggers</th></tr></thead>
        <tbody>${ruleRows.map(([label, row]) => `<tr><th>${label}</th><td>${row?.hits ?? "—"}</td><td>${row?.misses ?? "—"}</td><td>${row?.false ?? "—"}</td></tr>`).join("")}</tbody>
      </table>
      <p class="note"><b>Rainfall was “yes” in every place, so it told us almost nothing about which places flooded.</b> It disagreed with radar in ${radarNo} of the ${radarYes + radarNo} places radar could judge.</p>
      <p class="note">Requiring radar means ${rule.misses ?? "—"} of ${n} reported floods produced no claim: ${radarNo} where radar saw too little open water, and ${unassessed} where it could not look. Rainfall alone would have found all ${n}, but there is no “did not flood” place in this log, so we cannot say how often rainfall alone would raise a false alarm. Neither number is an accuracy figure.</p>
      <p class="note">Misses caused by radar having no pass that week: <b>${counts.misses?.no_scene ?? 0}</b>. The 6 May scene existed.</p>
      <table>
        <caption>Why the reported floods that produced no claim were missed</caption>
        <thead><tr><th></th><th>Places</th></tr></thead>
        <tbody>${missRows.map(([label, count]) => `<tr><th>${label}</th><td>${count}</td></tr>`).join("")}</tbody>
      </table>
    </div></section>
    <section class="block"><div class="wrap">
      <div class="sec-head"><span class="num">02</span><h2>The rule on the chain is the rule in the repository</h2></div>
      <p class="lede">Each claim id contains a hash of <code>config/rule.yaml</code>. The hash on the snapshot is <code>${esc(cache.rule?.thresholds_hash || "")}</code>. If someone had changed the rule after the fact, they would not match.</p>
      <p class="note">The file is stored byte for byte, line endings included, because the hash covers every byte.</p>
    </div></section>
    <section class="block alt"><div class="wrap">
      <div class="sec-head"><span class="num">03</span><h2>Download the data</h2></div>
      <p class="lede">These are copies of the repository files the numbers are computed from.</p>
      <ul class="limits">
        <li><b><a href="/data/counts.csv" download>counts.csv</a></b><span>Every count on this page · <code>backtest/results/counts.csv</code></span></li>
        <li><b><a href="/data/label_log.csv" download>label_log.csv</a></b><span>The seven places and the reports that named them</span></li>
        <li><b><a href="/data/radar_fractions.csv" download>radar_fractions.csv</a></b><span>Radar fraction and pixel counts per place</span></li>
        <li><b><a href="/data/observations.csv" download>observations.csv</a></b><span>What each source signed, per place</span></li>
        <li><b><a href="/data/rule.yaml" download>rule.yaml</a></b><span>The frozen rule, byte for byte</span></li>
      </ul>
    </div></section>
    <section class="block"><div class="wrap">
      <div class="sec-head"><span class="num">04</span><h2>Reproduce it</h2></div>
      <pre class="cmd"><code>python -m backtest.week --recipe
python -m backtest.week
python -m unittest backtest.test_score backtest.test_week backtest.pipeline.test_pipeline watcher.test_mirror
cd app
npm install
npm run build
python web/server.py</code></pre>
      <p class="note">The radar fractions come from <code>backtest/checks/radar_fraction.py</code>, which needs network access to Microsoft Planetary Computer. The site does not run that script. The scored result does not depend on rerunning it: the measured values are in the CSV above. A second week is allowed only if <code>config/rule.yaml</code> stays unchanged.</p>
    </div></section>
    <section class="block alt"><div class="wrap">
      <div class="sec-head"><span class="num">05</span><h2>What this cannot tell you</h2></div>
      <ul class="limits">
        <li><b>No “did not flood” labels.</b><span>Without them there are no false alarms to count, so no precision, and we publish none.</span></li>
        <li><b>Seven reports favour reachable places.</b><span>Unknown is not “no flood”.</span></li>
        <li><b>Boxes are not flood outlines.</b><span>A ward box mixes dry and wet land, which pulls the radar fraction down. That is one reason radar says no in ${radarNo} places.</span></li>
        <li><b>One week.</b><span>Nothing here says how the rule behaves in another season.</span></li>
      </ul>
    </div></section>
  `, "/backtest");
}

export function placePage(ctx, slug) {
  const { cache, esc, shell, weekLabel } = ctx;
  const place = (cache.places || []).find((p) => p.slug === slug);
  if (!place) {
    return shell("Not found — Aetheris", `
      <section class="block"><div class="wrap">
        <h1>That place is not in the files.</h1>
        <a class="btn primary" href="/claims">Claims</a>
      </div></section>
    `, "/claims");
  }
  const rain = cache.rainfall || {};
  const rule = cache.rule || {};
  const chain = cache.chain;
  const onChain = (chain?.claims || []).find((c) => c.zone === slug);
  return shell(`${place.name} — Aetheris`, `
    <section class="block"><div class="wrap">
      <p class="crumb"><a href="/claims">Claims</a> / ${esc(place.name)}</p>
      <h1>${esc(place.name)}, ${esc(weekLabel())}</h1>
      <p class="lede">${esc(place.scale)}</p>
      <div class="sheet">
        <p><span class="dot ${esc(place.marker)}"></span> <b>${esc(place.outcome)}</b></p>
        <p>${esc(place.snapshot)}. Snapshot at deploy. Live state is below, only if Sepolia answers.</p>
      </div>
      <p class="live-status" data-live-status>Reading Sepolia…</p>
      <div data-live-claim></div>
      <p class="txlog" data-tx-log hidden></p>
      <p class="note" data-sandbox><b>SANDBOX.</b> No Daraja call. No shillings moved.</p>
    </div></section>
    <section class="block alt"><div class="wrap">
      <div class="sec-head"><span class="num">01</span><h2>The reason for this decision</h2></div>
      <p class="lede">${esc(place.why)}</p>
      <div class="cards">
        <div class="card"><div class="body">
          <span class="who">Radar</span>
          <h3>${esc(place.radar)}</h3>
          ${radarBar(place, cache)}
          <p class="note">${place.land_pixels != null ? `${place.land_pixels.toLocaleString()} land pixels. ${place.flooded_pixels?.toLocaleString() ?? "—"} looked like water.` : "Not measured."}</p>
          <p class="note">${esc(place.box_note)}</p>
        </div></div>
        <div class="card"><div class="body">
          <span class="who">Rainfall</span>
          <h3>${esc(place.rain)}</h3>
          ${rainBar(cache)}
          <p class="note">${esc(rain.mm)} mm over the three days to 6 May. CHIRPS 2.0 daily, a satellite estimate. Upstream catchment <code>${esc(rain.catchment_id || "")}</code>, not this place. Line ${esc(rain.line_mm)} mm over ${esc(rain.window_days)} days, lag ${esc(rain.lag_days)} days.</p>
        </div></div>
      </div>
    </div></section>
    <section class="block"><div class="wrap">
      <div class="sec-head"><span class="num">02</span><h2>Why this place was counted as flooded</h2></div>
      <p class="lede">${esc(place.label_note)}</p>
      <p class="note"><a href="${esc(place.label_url)}">${esc(place.label_source)}</a>, reported 4–5 May 2024. A news report is a label, not a survey.</p>
    </div></section>
    <section class="block alt"><div class="wrap">
      <div class="sec-head"><span class="num">03</span><h2>What is on the testnet</h2></div>
      ${onChain ? `
        <p class="lede">${esc(onChain.state)}. Snapshot at ${esc(chain.snapshot_at)}.</p>
        <dl class="ids">
          <dt>Claim id</dt><dd><code>${esc(onChain.trigger_id)}</code></dd>
          ${(onChain.signers || []).map((s) => `<dt>${esc(s.role)}</dt><dd><code>${esc(s.evidence)}</code></dd>`).join("")}
        </dl>
      ` : `<p class="lede">No signature exists for this place. The rule did not fire here, so neither attester signed, and the contract holds nothing for it. Silence counts as no.</p>`}
      <p class="note">Writes go through your wallet on Sepolia. The referee cannot be an attester. Testnet only.</p>
    </div></section>
    <section class="block"><div class="wrap">
      <div class="sec-head"><span class="num">04</span><h2>The identifiers, so you can recompute them</h2></div>
      <p class="lede">The claim id is <code>keccak256(zoneId, eventWeek, ruleId, thresholdsHash)</code>. Change the rule and the id changes.</p>
      <dl class="ids">
        <dt>Claim id</dt><dd><code>${esc(place.claim_id)}</code></dd>
        <dt>Zone id</dt><dd><code>${esc(place.zone_id)}</code> = keccak256(“${esc(place.slug)}”)</dd>
        <dt>Event week</dt><dd><code>${esc(rule.week_id || "")}</code></dd>
        <dt>Rule id</dt><dd><code>${esc(rule.rule_id)}</code> = keccak256(“${esc(rule.id)}”)</dd>
        <dt>Thresholds hash</dt><dd><code>${esc(rule.thresholds_hash)}</code> = keccak256(config/rule.yaml)</dd>
      </dl>
    </div></section>
  `, "/claims");
}
