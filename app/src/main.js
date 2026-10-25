import "./styles.css";
import { desk, leave, me } from "./api.js";
import { focusBox, mountKenyaMap } from "./map.js";
import { afterPage, onAct, onWalletClick, paintWalletButton } from "./live.js";
import { backtestPage, claimsPage, methodPage, normalizePath, placePage } from "./pages.js";

const DESKS = [
  { id: "data", href: "/desk/data", who: "ICPAC / Kenya Met", title: "The files", blurb: "Pixels, rain, and which names have no outline." },
  { id: "insurer", href: "/desk/insurer", who: "Insurer", title: "Pay or not", blurb: "What the rule said this week. Rain alone never pays." },
  { id: "reinsurer", href: "/desk/reinsurer", who: "Reinsurer", title: "This one flood", blurb: "One named event. Not a catalogue of years." },
  { id: "responder", href: "/desk/responder", who: "Responders / county", title: "Before funds or an alert", blurb: "A second instrument, and a record you can defend. Not the official forecast." },
  { id: "research", href: "/desk/research", who: "Research", title: "The method", blurb: "Counts, the frozen rule, and the files. No machine learning." },
  { id: "farmer", href: "/desk/farmer", who: "Smallholders", title: "The reason", blurb: "A checkable reason for each decision. A sandbox message if the demo releases a payout. They do not use this app." },
];

const DESK_NAV = {
  data: [
    { href: "/desk/data", label: "This week" },
    { href: "/method", label: "How it is measured" },
  ],
  insurer: [
    { href: "/desk/insurer", label: "This week" },
    { href: "/backtest", label: "Backtest" },
    { href: "/claims", label: "Claims" },
  ],
  reinsurer: [
    { href: "/desk/reinsurer", label: "This event" },
    { href: "/claims", label: "Places" },
  ],
  responder: [
    { href: "/desk/responder", label: "Decision" },
    { href: "/method", label: "Limits" },
  ],
  research: [
    { href: "/desk/research", label: "Files" },
    { href: "/method", label: "Method" },
    { href: "/claims", label: "Claims" },
    { href: "/backtest", label: "Backtest" },
  ],
  farmer: [
    { href: "/desk/farmer", label: "The reason" },
    { href: "/method", label: "Who this is for" },
  ],
};

let cache = null;
let viewer = null;
let theme = "light";
let phoneMode = "idle";
let phoneSlug = "";
let phoneBuffer = "";
let phoneLang = "en";

function $(sel, root = document) {
  return root.querySelector(sel);
}

function themeNow() {
  try {
    return localStorage.getItem("aetheris-theme") === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

function setTheme(next) {
  theme = next;
  document.documentElement.setAttribute("data-theme", next);
  try {
    localStorage.setItem("aetheris-theme", next);
  } catch {
    /* ignore */
  }
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function pathOf() {
  return normalizePath(location.pathname.replace(/\/$/, "") || "/");
}

function go(href, replace = false) {
  const next = normalizePath(href);
  if (replace) history.replaceState({}, "", next);
  else history.pushState({}, "", next);
  render();
}

async function load() {
  const [who, data] = await Promise.all([me(), desk()]);
  viewer = who && who.ok ? who : null;
  cache = data;
}

function deskIdOf(path) {
  if (path.startsWith("/desk/")) return path.split("/")[2] || "";
  return viewer?.desk || "";
}

function linksFor(path) {
  if (path === "/" || path === "/enter" || path === "/desks") return [];
  const id = deskIdOf(path);
  if (id && DESK_NAV[id]) return DESK_NAV[id];
  if (viewer?.desk && DESK_NAV[viewer.desk]) return DESK_NAV[viewer.desk];
  return [];
}

function shell(title, inner, active) {
  document.title = title;
  const path = pathOf();
  const door = path === "/" || path === "/enter" || path === "/desks";
  const links = linksFor(path);
  const id = deskIdOf(path);
  const deskName = viewer?.role_label || DESKS.find((d) => d.id === id)?.who || "";
  const nav = links.length
    ? `<nav class="nav">${links.map((item) => `<a href="${item.href}" class="${item.href === active ? "on" : ""}">${item.label}</a>`).join("")}</nav>`
    : "";
  const onChain = path === "/claims" || path.startsWith("/claim/");
  let tools = `<button type="button" class="btn small" data-theme>${theme === "dark" ? "Light mode" : "Dark mode"}</button>`;
  if (onChain) tools += `<button type="button" class="btn small" data-wallet>Connect wallet</button>`;
  if (viewer && !door) {
    tools = `<span class="who">${esc(viewer.role_label)}</span>${tools}<button type="button" class="btn small" data-leave>Leave</button>`;
  } else if (!door && !viewer) {
    tools += `<a class="btn small primary" href="/enter">Enter a desk</a>`;
  }
  const root = path === "/desk/responder" ? "ops" : "page";
  return `
    <div class="${root}">
    <div class="band"><div class="wrap">
      <span>Nyando basin · Kenya</span>
      <span>IEEE ClimateChain 2026 · testnet only</span>
    </div></div>
    <header class="mast${door ? " door" : " desk"}"><div class="wrap">
      <a class="mark" href="/">Aetheris ${deskName && !door ? `<span>${esc(deskName)}</span>` : "<span>Nyando</span>"}</a>
      ${nav}
      <div class="tools">${tools}</div>
    </div></header>
    ${inner}
    <footer><div class="wrap">
      <p>Verification layer, not a forecast. Sentinel-1 and CHIRPS from the files. Sepolia testnet. M-PESA Daraja sandbox. Pictures are decorative, not the 6 May 2024 scene.</p>
    </div></footer>
    </div>
  `;
}

function landing() {
  const places = cache?.places || [];
  const radarYes = cache?.radar?.signed ?? places.filter((p) => p.radar === "yes").length;
  const rainYes = cache?.rainfall?.signed ?? places.filter((p) => p.rain === "yes").length;
  const unknown = cache?.radar?.no_geometry ?? places.filter((p) => p.radar === "abstain").length;
  const opened = places.filter((p) => p.both === "yes");
  const openedName = opened.map((p) => p.name).join(", ") || "none";
  return shell("Aetheris — Nyando flood data", `
    <section class="hero">
      <div>
        <img src="/media/hero-basin.jpg" alt="">
        <p class="img-note">Decorative photograph. Not the 6 May 2024 Sentinel-1 scene.</p>
      </div>
      <div class="hero-copy">
        <p class="eyebrow">Nyando basin, Kenya · 4–6 May 2024</p>
        <h1>Rain said flood in ${places.length} places. Radar agreed in ${radarYes}.</h1>
        <p class="lede">After a flood, insurance and alerts often trust a rainfall number. That number can be wrong. Aetheris puts the rain number next to a radar picture of open water, for a named place, and writes down whether they agree. No machine learning. This is a demo. No real money moves.</p>
        <div class="cta">
          <a class="btn primary" href="/enter">1. Enter as insurer</a>
          <a class="btn" href="/claim/kabonyo-kanyagwal">2. Open Kabonyo</a>
        </div>
      </div>
    </section>
    <section class="block"><div class="wrap">
      <div class="sec-head"><span class="num">01</span><h2>What we check</h2></div>
      <p class="lede">One question, asked twice, about the same week.</p>
      <ol class="how">
        <li>
          <img src="/media/strip-rain.jpg" alt="">
          <div>
            <span class="who">Rain</span>
            <h3>Was there enough rain?</h3>
            <p>A satellite rainfall product looks at the river’s headwaters. Enough rain can sign. Rain alone never opens a claim.</p>
          </div>
        </li>
        <li>
          <img src="/media/strip-water.jpg" alt="">
          <div>
            <span class="who">Radar</span>
            <h3>Does the land look wet?</h3>
            <p>A radar satellite looks for open water on that place. If we have no outline for the name, we do not guess. Unknown is not “no flood”.</p>
          </div>
        </li>
        <li>
          <img src="/media/desk-field.jpg" alt="">
          <div>
            <span class="who">Both</span>
            <h3>Only both can open a claim.</h3>
            <p>If rain and radar both sign, a claim can open on a test network so anyone can read it or challenge it.</p>
          </div>
        </li>
      </ol>
    </div></section>
    <section class="block alt"><div class="wrap">
      <div class="sec-head"><span class="num">02</span><h2>What this week said</h2></div>
      <p class="lede">News named ${places.length} places as flooded. We did not survey them. We asked the two sources what they signed.</p>
      <ul class="stats">
        <li><img src="/media/strip-rain.jpg" alt=""><div><p class="n rain">${rainYes}</p><p>Rain signed “flood” here</p></div></li>
        <li><img src="/media/strip-water.jpg" alt=""><div><p class="n radar">${radarYes}</p><p>Radar also signed</p></div></li>
        <li><div><p class="n">${opened.length}</p><p>Both signed, so a claim may open${opened.length ? ` · ${esc(openedName)}` : ""}</p></div></li>
        <li><div><p class="n">${unknown}</p><p>We could not look. No outline, so no radar reading</p></div></li>
      </ul>
      <p class="note">These are counts from the files. They are not an accuracy score. Three names had no outline we would measure, so radar was not run there.</p>
      <ol class="steps walk">
        <li><b><a href="/enter">Enter as insurer.</a></b> Rain would have paid ${rainYes}. This rule paid ${opened.length}.</li>
        <li><b><a href="/claim/kabonyo-kanyagwal">Open Kabonyo-Kanyagwal.</a></b> The one place both sources signed. Read Sepolia. Challenge or finalize from your wallet.</li>
        <li><b><a href="/backtest">Open the backtest.</a></b> Agreements, disagreements, found, missed. False triggers stay 0: no “did not flood” labels.</li>
        <li><b><a href="/claims">Open claims and the escrow.</a></b> Testnet only. Pays once, after Finalized. No hand-release. M-PESA is SANDBOX.</li>
      </ol>
    </div></section>
    <section class="block"><div class="wrap">
      <div class="sec-head"><span class="num">03</span><h2>Pick who you are</h2></div>
      <p class="lede">Each desk is the same week, shown for a different job. There is no password. You are not creating an account.</p>
      <div class="cards">${DESKS.map(deskCard).join("")}</div>
    </div></section>
    <section class="block alt"><div class="wrap">
      <div class="sec-head"><span class="num">04</span><h2>What this is not</h2></div>
      <ul class="limits">
        <li><b>Not a forecast.</b><span>It is a check of one week that already happened.</span></li>
        <li><b>Not an accuracy percentage.</b><span>Seven news reports cannot carry one. We publish counts.</span></li>
        <li><b>Not real money.</b><span>Testnet tokens. M-PESA is a sandbox. The contracts are unaudited.</span></li>
        <li><b>Pictures are not evidence.</b><span>The photographs are decorative. They are not the radar scene.</span></li>
      </ul>
    </div></section>
  `, "/");
}

function deskCard(d) {
  return `
    <article class="card">
      <div class="body">
        <span class="who">${d.who}</span>
        <h3>${d.title}</h3>
        <p>${d.blurb}</p>
        <p class="cta"><a class="btn primary" href="${d.href}">Enter as ${d.who}</a></p>
      </div>
    </article>`;
}

function enterPage() {
  const already = viewer
    ? `<p class="status">You are already at the ${esc(viewer.role_label)} desk. <a href="${esc(viewer.home)}">Open it</a>.</p>`
    : "";
  return shell("Enter — Aetheris", `
    <section class="block"><div class="wrap enter-head">
      <p class="eyebrow">No password · not an account</p>
      <h1>Who are you here as?</h1>
      <p class="lede">Same week, six jobs. Open a desk. You can leave whenever you want.</p>
      ${already}
    </div></section>
    <section class="block alt"><div class="wrap">
      <div class="cards desk-grid">${DESKS.map(deskCard).join("")}</div>
    </div></section>
  `, "/enter");
}

function desksPage() {
  return shell("Desks — Aetheris", `
    <section class="block"><div class="wrap">
      <div class="sec-head"><span class="num">Desks</span><h2>Same week. Different job.</h2></div>
      <p class="lede">Each desk reads the same /api/desk payload. The numbers do not change by role.</p>
      <div class="cards">${DESKS.map(deskCard).join("")}</div>
    </div></section>
  `, "/desks");
}

function placeRows(places) {
  return places.map((p) => `
    <tr>
      <td>${esc(p.name)}</td>
      <td>${esc(p.radar)}</td>
      <td>${esc(p.rain)}</td>
      <td>${esc(p.both)}</td>
      <td>${esc(p.pixels ?? "—")}</td>
      <td>${p.box ? "yes" : "no"}</td>
    </tr>`).join("");
}

function mapSvg(places) {
  const boxed = places.filter((p) => p.box && p.zone);
  if (!boxed.length) return "";
  const xs = boxed.flatMap((p) => [p.zone.min_lon, p.zone.max_lon]);
  const ys = boxed.flatMap((p) => [p.zone.min_lat, p.zone.max_lat]);
  const minX = Math.min(...xs) - 0.02;
  const maxX = Math.max(...xs) + 0.02;
  const minY = Math.min(...ys) - 0.02;
  const maxY = Math.max(...ys) + 0.02;
  const w = 480;
  const h = 320;
  const sx = (x) => ((x - minX) / (maxX - minX)) * w;
  const sy = (y) => (1 - (y - minY) / (maxY - minY)) * h;
  const boxes = boxed.map((p) => {
    const z = p.zone;
    const x = sx(z.min_lon);
    const y = sy(z.max_lat);
    const bw = sx(z.max_lon) - x;
    const bh = sy(z.min_lat) - y;
    const cls = p.radar === "yes" ? "box yes" : "box";
    return `<g class="${cls}" data-slug="${esc(p.slug)}"><rect x="${x}" y="${y}" width="${bw}" height="${bh}"></rect><text x="${x + 4}" y="${y + 14}" fill="currentColor" font-size="11">${esc(p.name)}</text></g>`;
  }).join("");
  return `<svg class="basin" viewBox="0 0 ${w} ${h}" role="img">${boxes}</svg>`;
}

function weekLabel() {
  const week = cache?.week;
  if (typeof week === "string" && week) return week;
  return week?.label || week?.start || "4–6 May 2024";
}

function deskLayout(id, title, lead, extra) {
  const places = cache?.places || [];
  const miss = cache?.miss || places.filter((p) => !p.box && !p.has_outline);
  return shell(title, `
    <section class="block tight"><div class="wrap">
      <p class="eyebrow">${esc(weekLabel())} · Nyando basin</p>
      <h1>${esc(title)}</h1>
      <p class="lede">${lead}</p>
      ${extra}
    </div></section>
    <section class="block alt"><div class="wrap desk-split">
      <div>
        <div class="map-tools">
          <button type="button" class="btn small" data-zoom="kenya">Kenya</button>
          <button type="button" class="btn small" data-zoom="basin">Nyando boxes</button>
        </div>
        <div id="kenya-map" role="img" aria-label="OpenStreetMap of Kenya. Only places with an outline are drawn."></div>
        <p class="note">OpenStreetMap. Four working boxes only. Boxes overlap because they are ward extents, not flood outlines. We do not invent a box for a name without geometry.</p>
        <div class="place-list">
          ${places.map((p) => `
            <button type="button" data-slug="${esc(p.slug)}">
              <b>${esc(p.name)}</b>
              <span>${p.zone ? "On the map" : "No outline. Not drawn."}</span>
            </button>`).join("")}
        </div>
        ${miss.length ? `<p class="note">Not drawn: ${miss.map((m) => esc(m.name || m)).join(", ")}.</p>` : ""}
      </div>
      <div data-place></div>
    </div></section>
  `, `/desk/${id}`);
}

function showPlace(slug) {
  const place = (cache?.places || []).find((p) => p.slug === slug);
  const hold = $("[data-place]");
  if (!place || !hold) return;
  document.querySelectorAll(".place-list button, .picks button").forEach((b) => {
    b.classList.toggle("on", b.dataset.slug === slug);
  });
  focusBox(slug);
  if (pathOf() === "/desk/insurer") {
    hold.innerHTML = insurerSheet(place);
    return;
  }
  if (pathOf() === "/desk/reinsurer") {
    hold.innerHTML = reinsurerSheet(place);
    return;
  }
  const loss = place.loss || {};
  hold.innerHTML = `
    <div class="sheet">
      <h3>${esc(place.name)}</h3>
      <p class="note">${esc(place.outcome || "")}. ${esc(place.scale || "")}</p>
      <div class="grid">
        <div><span class="k">Radar</span>${esc(place.radar)}</div>
        <div><span class="k">Rain</span>${esc(place.rain)}</div>
        <div><span class="k">This rule</span>${esc(place.both === "yes" ? "Would open a claim" : place.radar === "abstain" ? "Cannot assess" : "No claim")}</div>
      </div>
      ${loss.ground_up_label && loss.ground_up_label !== "—" ? `<p class="note">${esc(loss.class_label || "")} ${esc(loss.ground_up_label)}</p>` : ""}
      <p class="cta"><a class="btn" href="/claim/${esc(place.slug)}">Open this place</a></p>
    </div>`;
}

function insurerSheet(place) {
  const rainPay = place.rain === "yes" ? "Would have paid" : "Would not have paid";
  let rulePay = "Cannot assess";
  if (place.radar === "yes" && place.rain === "yes") rulePay = "Would open a claim";
  else if (place.radar === "no") rulePay = "Rainfall only — no claim";
  const frac = place.fraction == null ? "Not measured" : `${(place.fraction * 100).toFixed(1)}% of land pixels`;
  return `
    <div class="sheet">
      <span class="who">${esc(place.scale)}</span>
      <h3>${esc(place.name)}</h3>
      <p><span class="dot ${esc(place.marker)}"></span> ${esc(place.outcome)}</p>
      <p class="note">${esc(place.why)}</p>
      <div class="grid">
        <div><span class="k">Rainfall trigger</span>${esc(rainPay)}</div>
        <div><span class="k">This rule</span>${esc(rulePay)}</div>
        <div><span class="k">Radar</span>${esc(frac)}</div>
        <div><span class="k">On the testnet</span>${esc(place.snapshot)}</div>
      </div>
      <p class="cta"><a class="btn primary" href="/claim/${esc(place.slug)}">Open this place</a></p>
    </div>`;
}

function dataDesk() {
  const places = cache?.places || [];
  const rain = cache?.rainfall || {};
  const radar = cache?.radar || {};
  const rows = places.map((p) => {
    const frac = p.fraction == null ? "Not measured" : `${(p.fraction * 100).toFixed(1)}%`;
    const geom = p.zone ? "OSM box" : "No outline";
    return `<tr><th>${esc(p.name)}</th><td>${esc(p.radar)}</td><td>${esc(frac)}</td><td>${esc(p.rain)}</td><td>${esc(geom)}</td><td>${esc(p.land_pixels ?? "—")}</td></tr>`;
  }).join("");
  return deskLayout(
    "data",
    "Where rain and radar disagreed",
    "Same CSVs as the scorer. Radar is the reference for this check, not ground truth. No gauges. Not a flood forecast.",
    `<ul class="stats">
      <li><div><p class="n rain">${esc(rain.mm ?? "—")} mm</p><p>One catchment, ${esc(rain.product || "CHIRPS")}. Line ${esc(rain.line_mm ?? 40)} mm / ${esc(rain.window_days ?? 3)} days.</p></div></li>
      <li><div><p class="n radar">${radar.signed ?? 0}</p><p>Radar signed. ${radar.below ?? 0} under the line. ${radar.no_geometry ?? 0} not measured.</p></div></li>
    </ul>
    <table>
      <caption>Seven news-named places. Radar fraction is not flood depth.</caption>
      <thead><tr><th>Place</th><th>Radar</th><th>Open water</th><th>Rain</th><th>Geometry</th><th>Land pixels</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="note">Four OSM boxes only. We do not invent a box. <a href="/data/radar_fractions.csv">radar_fractions.csv</a> · <a href="/data/observations.csv">observations.csv</a></p>`,
  );
}

function insurerDesk() {
  const places = cache?.places || [];
  const rainYes = cache?.rainfall?.signed ?? places.filter((p) => p.rain === "yes").length;
  const paid = places.filter((p) => p.both === "yes").length;
  const rule = cache?.counts?.rules?.radar_plus_rainfall || {};
  const rainOnly = cache?.counts?.rules?.rainfall_only || {};
  return deskLayout(
    "insurer",
    `Rain would have paid ${rainYes}. This rule paid ${paid}.`,
    "For each named place this week: whether radar and rainfall agreed, who signed, and whether anything was disputed. Use the counts to design a trigger. This is not a certified insurance product and not an accuracy figure.",
    `<ul class="stats">
      <li><div><p class="n">${rule.hits ?? paid}</p><p>This rule found</p></div></li>
      <li><div><p class="n">${rule.misses ?? "—"}</p><p>This rule missed</p></div></li>
      <li><div><p class="n">${rule.false ?? 0}</p><p>False triggers (none to count: no “did not flood” labels)</p></div></li>
      <li><div><p class="n rain">${rainOnly.hits ?? rainYes}</p><p>Rainfall-only would have found</p></div></li>
    </ul>
    <p class="note">One week. Seven news-named places. <a href="/backtest">Open the full backtest</a>.</p>`,
  );
}

function grantEth(n) {
  const unit = Number(cache?.loss?.grant_eth || 0.001);
  return `${(n * unit).toFixed(3)} ETH`;
}

function layerOf(place) {
  if (place.both === "yes" || place.modeled) {
    return { id: "modeled", tag: "Modeled on this rule" };
  }
  return { id: "residual", tag: "Unmodeled residual" };
}

function reinsurerDesk() {
  const places = cache?.places || [];
  const rain = cache?.rainfall || {};
  const radar = cache?.radar || {};
  const loss = cache?.loss || {};
  const modeled = places.filter((p) => p.both === "yes" || p.modeled).length;
  const residual = places.length - modeled;
  const rainMm = rain.mm != null ? `${rain.mm} mm` : "—";
  return deskLayout(
    "reinsurer",
    `${weekLabel()}. One event. Not a catastrophe model.`,
    "A cat model needs thousands of simulated years, a vulnerability function, and your own exposure file. This desk is the footprint of one named flood, layered the way you already read an event: hazard, exposure, modeled loss, and the residual the rule left out. Put it in your model. Do not treat this as the model.",
    `<ul class="stats">
      <li><div><p class="n rain">${esc(rainMm)}</p><p>Hazard · one catchment rain reading. Radar signed in ${radar.signed ?? 0} of ${places.length}.</p></div></li>
      <li><div><p class="n">${esc(loss.tiv_label || "—")}</p><p>Exposure · stand-in TIV on ${loss.places_with_tiv ?? 0} places with a printed household count.</p></div></li>
      <li><div><p class="n radar">${modeled}</p><p>Modeled loss · ${grantEth(modeled)} demo grant. Indicative ground-up ${esc(loss.ground_up_label || "—")}.</p></div></li>
      <li><div><p class="n rain">${residual}</p><p>Unmodeled residual · reported floods the rule did not open. Not a return period.</p></div></li>
    </ul>
    <ul class="limits">
      <li><b>No stochastic catalogue.</b><span>One week. No average annual loss, no EP curve, no PML, no return period.</span></li>
      <li><b>No measured depth map.</b><span>Waist-high at Ahero, taken as ${loss.depth_m ?? 0.9} m. That number is borrowed at the other six. Radar fraction is not depth.</span></li>
      <li><b>TIV is a stand-in.</b><span>${loss.households ?? 0} households × a Kakuma UNHCR shelter grant. Four places have no TIV. Load your own sums insured.</span></li>
      <li><b>We have not interviewed a reinsurer.</b><span>The layers are an assumption about how you already read a flood.</span></li>
    </ul>
    <p class="note">Pick a box or a name. That place’s four layers open on the right.</p>`,
  );
}

function reinsurerSheet(place) {
  const loss = place.loss || place;
  const layer = layerOf(place);
  const rainMm = cache?.rainfall?.mm;
  const rainLine = cache?.rainfall?.line_mm;
  const rainWord = place.rain === "yes"
    ? `Signed. ${rainMm ?? "—"} mm against ${rainLine ?? 40} mm / 3 days.`
    : "Did not sign.";
  const frac = place.fraction == null
    ? "Not measured. No outline."
    : `${(place.fraction * 100).toFixed(1)}% of land pixels against a ${(Number(cache?.radar?.line ?? 0.05) * 100).toFixed(1)}% line.`;
  const depth = loss.depth_m == null ? "—" : `${loss.depth_m} m · ${loss.depth_provenance || ""}`;
  const book = loss.households
    ? `${loss.households_note || `${loss.households} households`} · TIV ${loss.tiv_label || "—"}`
    : (loss.households_note || "No printed household count, so no TIV.");
  const ratio = loss.damage_ratio == null ? "—" : Number(loss.damage_ratio).toFixed(2);
  const ground = loss.ground_up_label && loss.ground_up_label !== "—"
    ? `${loss.ground_up_label} · ratio ${ratio} of TIV`
    : "No ground-up. No TIV to multiply.";
  const residual = place.radar === "abstain"
    ? "No outline we would stand behind. Radar was not run. The report still stands."
    : "Radar stayed under the line. The news-named flood is the residual.";
  return `
    <div class="sheet ${layer.id === "residual" ? "hold" : ""}">
      <span class="who">${esc(place.scale)} · ${esc(layer.tag)}</span>
      <h3>${esc(place.name)}</h3>
      <p><span class="dot ${esc(place.marker)}"></span> ${esc(place.outcome)}</p>
      <div class="grid">
        <div><span class="k">01 Hazard · rain</span>${esc(rainWord)}</div>
        <div><span class="k">01 Hazard · radar</span>${esc(frac)}</div>
        <div><span class="k">02 Exposure</span>${esc(book)}</div>
        <div><span class="k">03 Vulnerability</span>${esc(depth)}. ${esc(loss.class_label || "")}. ${esc(loss.curve_label || "JRC adapted")}. Radar fraction is not used as depth.</div>
        <div><span class="k">04 ${layer.id === "modeled" ? "Modeled loss" : "Unmodeled residual"}</span>${esc(layer.id === "modeled" ? `${ground} Demo grant ${grantEth(1)}.` : residual)}</div>
      </div>
      <p class="note">${esc(place.why || "")}</p>
      <p class="cta"><a class="btn primary" href="/claim/${esc(place.slug)}">Open this place</a></p>
    </div>`;
}

function actionOf(place) {
  if (!place.box || place.radar === "abstain") {
    return {
      id: "stop",
      tag: "Cannot defend",
      line: "No outline. The report still stands. Do not release, and do not call this dry.",
    };
  }
  if (place.radar === "yes" && place.rain === "yes") {
    return {
      id: "go",
      tag: "Second signal",
      line: "Radar and rainfall both signed. This record can support releasing funds or an alert.",
    };
  }
  if (place.radar === "no") {
    return {
      id: "hold",
      tag: "Do not release",
      line: "Rain signed for the basin. Radar did not. Do not release funds or an alert from this screen.",
    };
  }
  return {
    id: "hold",
    tag: "Do not release",
    line: "Only one source signed. Do not release funds or an alert from this screen.",
  };
}

const RADAR_SCENE = "S1A_IW_GRDH_1SDV_20240506T155655_20240506T155720_053752_068803_rtc";

function countLabel(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("en-US");
}

function pctLabel(fraction) {
  const n = Number(fraction);
  if (!Number.isFinite(n)) return null;
  return `${(n * 100).toFixed(1)}%`;
}

function sayThis(place) {
  const action = actionOf(place);
  if (action.id === "go") {
    return "Both instruments signed. A county officer can point at this record. It is not the Kenya Meteorological Department forecast.";
  }
  if (action.id === "stop") {
    return "No radar reading. Do not release funds or an alert, and do not tell people a blank map means dry.";
  }
  return "A report says this place flooded. The second instrument did not sign. Do not release funds or an alert from this screen.";
}

function metricBits(place) {
  const line = pctLabel(cache?.radar?.line ?? 0.05) || "5.0%";
  if (!place.box || place.radar === "abstain") {
    return { water: "Not measured", line: "—", scale: place.scale || "—" };
  }
  return {
    water: pctLabel(place.fraction) || "—",
    line,
    scale: place.scale || "—",
  };
}

function responderCard(place) {
  const action = actionOf(place);
  const bits = metricBits(place);
  const source = place.label_url
    ? `<p class="meta">Source: <a href="${esc(place.label_url)}">${esc(place.label_source || "report")}</a></p>`
    : "";
  return `<article class="act-card ${action.id}">
    <button type="button" data-slug="${esc(place.slug)}">
      <span class="badge">${esc(action.tag)}</span>
      <h3>${esc(place.name)}</h3>
      <div class="card-split">
        <dl class="metrics">
          <div><dt>Open water</dt><dd>${esc(bits.water)}</dd></div>
          <div><dt>Line</dt><dd>${esc(bits.line)}</dd></div>
          <div><dt>Report scale</dt><dd>${esc(bits.scale)}</dd></div>
        </dl>
        <p class="report">${esc(place.label_note || "")}</p>
      </div>
    </button>
    ${source}
  </article>`;
}

function responderColumn(title, tone, places) {
  const cards = places.map(responderCard).join("");
  return `<section class="lane ${tone}">
    <h2><span class="count">${places.length}</span> ${esc(title)}</h2>
    ${cards || `<p class="note">None this week.</p>`}
  </section>`;
}

function responderBrief() {
  const rain = cache?.rainfall || {};
  const radar = cache?.radar || {};
  const days = rain.window_days || 3;
  return `<div class="brief">
    <div><span class="k">Rain on every place</span><p>${esc(rain.mm ?? "—")} mm over ${esc(days)} days. The line is ${esc(rain.line_mm ?? 40)} mm. One catchment, so rain does not pick the ward.</p></div>
    <div><span class="k">Radar on 6 May</span><p>${esc(radar.signed ?? "—")} signed, ${esc(radar.below ?? "—")} under the line, ${esc(radar.no_geometry ?? "—")} not measured.</p></div>
    <div><span class="k">Not an official alert</span><p>Kenya Met still forecasts. Rain and radar describe the same storm. This is a second instrument, not a second witness.</p></div>
  </div>`;
}

function responderDesk() {
  const places = cache?.places || [];
  const go = places.filter((p) => actionOf(p).id === "go");
  const hold = places.filter((p) => actionOf(p).id === "hold");
  const stop = places.filter((p) => actionOf(p).id === "stop");
  const undrawn = stop.map((p) => esc(p.name)).join(", ");
  return shell("Decision — responders and policymakers", `
    <section class="block tight"><div class="wrap">
      <p class="eyebrow">${esc(weekLabel())} · Nyando · responders and policymakers</p>
      <h1>A second instrument before funds or an alert.</h1>
      <p class="lede">Open a place. The line says whether this record can support a release. The list under it is the evidence: scene, pixels, rain, the frozen rule, and whether a claim opened. This page does not replace an official forecast or an official alert.</p>
      ${responderBrief()}
      <p class="note">Start Ready describes releasing funds for <a href="https://www.anticipation-hub.org/Documents/Other/START_READY_-_2_pager.pdf">timely, effective action</a>. The IFRC brief <a href="https://disasterlaw.ifrc.org/media/4430">From Alert to Action</a> is for policymakers: a trigger, and accountability to the people at risk. We have not interviewed a county officer.</p>
    </div></section>
    <section class="block"><div class="wrap">
      <div class="action-board">
        ${responderColumn("can support a release", "go", go)}
        ${responderColumn("do not release", "hold", hold)}
        ${responderColumn("cannot defend", "stop", stop)}
      </div>
      <p class="note">Household counts are what the newspapers printed. Radar sees open water only. Water under crops, trees, or buildings does not sign. The fraction is not water over a doorway.</p>
    </div></section>
    <section class="block alt"><div class="wrap">
      <h2>Boxes we could draw</h2>
      <p class="lede">Teal is a second signal. Amber is rainfall only. A name without an outline stays off the map. Missing is not dry.</p>
      <div class="map-tools">
        <button type="button" class="btn small" data-zoom="kenya">Kenya</button>
        <button type="button" class="btn small" data-zoom="basin">Nyando boxes</button>
      </div>
      <div id="kenya-map" role="img" aria-label="OpenStreetMap. Teal boxes have a second signal. Amber boxes are rainfall only. Places without an outline are not drawn."></div>
      <p class="note">OpenStreetMap. The boxes are ward and town extents, not flood outlines.${undrawn ? ` Not drawn: ${undrawn}.` : ""}</p>
      <div data-place></div>
    </div></section>
  `, "/desk/responder");
}

function auditTrail(place) {
  const rule = cache?.rule || {};
  const chain = cache?.chain;
  const opened = place.radar === "yes" && place.rain === "yes";
  const claim = opened ? (place.claim_id || "—") : "No claim opened at deploy.";
  const trigger = chain?.explorer && chain?.trigger
    ? `<a href="${esc(chain.explorer)}/address/${esc(chain.trigger)}"><code>${esc(chain.trigger)}</code></a>`
    : "No deploy record in the files.";
  return `<details class="audit">
    <summary>Audit trail</summary>
    <dl class="ids">
      <dt>Radar scene</dt><dd><code>${esc(RADAR_SCENE)}</code></dd>
      <dt>Frozen rule</dt><dd><code>${esc(rule.rule_id || "—")}</code><code>${esc(rule.thresholds_hash || "")}</code></dd>
      <dt>Catchment id</dt><dd><code>${esc(cache?.rainfall?.catchment_id || "—")}</code></dd>
      <dt>Claim</dt><dd><code>${esc(claim)}</code></dd>
      <dt>Deploy snapshot</dt><dd>${esc(place.snapshot || "—")}</dd>
      <dt>Trigger contract</dt><dd>${trigger}</dd>
    </dl>
  </details>`;
}

function showResponder(slug) {
  const place = (cache?.places || []).find((p) => p.slug === slug);
  const hold = $("[data-place]");
  if (!place || !hold) return;
  const action = actionOf(place);
  document.querySelectorAll(".act-card").forEach((card) => {
    const button = card.querySelector("[data-slug]");
    card.classList.toggle("on", button && button.dataset.slug === slug);
  });
  const rainScope = cache?.rainfall?.scope || "One upstream catchment, applied to every place";
  const rain = cache?.rainfall || {};
  const drawn = place.zone
    ? "This box is on the map. It is the place extent we measured, not a flood outline."
    : "Not drawn. We do not invent a box for a name without an outline.";
  const bits = metricBits(place);
  const pixels = place.box
    ? `${countLabel(place.flooded_pixels)} flooded of ${countLabel(place.land_pixels)} land pixels. Permanent water removed: ${countLabel(place.removed)}.`
    : "No pixels. Radar was not run.";
  hold.innerHTML = `
    <div class="sheet ${action.id}">
      <span class="badge">${esc(action.tag)}</span>
      <h3>${esc(place.name)}</h3>
      <div class="card-split">
        <dl class="metrics">
          <div><dt>Open water</dt><dd>${esc(bits.water)}</dd></div>
          <div><dt>Line</dt><dd>${esc(bits.line)}</dd></div>
          <div><dt>Rain</dt><dd>${esc(rain.mm ?? "—")} mm · ${esc(place.rain)}</dd></div>
          <div><dt>Pixels</dt><dd>${esc(pixels)}</dd></div>
        </dl>
        <div>
          <p class="say">${esc(sayThis(place))}</p>
          <p>${esc(action.line)}</p>
          <p class="note">${esc(place.box_note || "")} ${esc(drawn)} ${esc(rainScope)}</p>
        </div>
      </div>
      ${auditTrail(place)}
    </div>`;
  if (place.zone) focusBox(slug);
}

function researchDesk() {
  const rule = cache?.rule || {};
  return deskLayout(
    "research",
    "An open method you can rerun",
    "Frozen rule, label log, counts. One week. Indicative, not a finished validation study. No machine learning. Do not tune thresholds on this season.",
    `<ul class="stats">
      <li><div><p class="n">${esc(rule.frozen_on || "—")}</p><p>Rule frozen. Hash ${esc(rule.thresholds_hash || "")}</p></div></li>
    </ul>
    <p class="cta">
      <a class="btn primary" href="/method">Method</a>
      <a class="btn" href="/backtest">Backtest</a>
      <a class="btn" href="/claims">Claims</a>
    </p>
    <ul class="limits">
      <li><b><a href="/data/counts.csv">counts.csv</a></b><span>Found, missed, false. False stays 0: no dry labels.</span></li>
      <li><b><a href="/data/label_log.csv">label_log.csv</a></b><span>The seven names and the reports.</span></li>
      <li><b><a href="/data/rule.yaml">rule.yaml</a></b><span>Byte for byte. That file’s hash is in every claim id.</span></li>
    </ul>
    <pre class="cmd"><code>python -m backtest.score
python -m unittest backtest.test_score backtest.pipeline.test_pipeline watcher.test_mirror</code></pre>`,
  );
}

const PHONE_COPY = {
  en: {
    idleHint: "No smartphone",
    idleCode: "Flood check",
    idleSub: "Press Call",
    menuTitle: "Nyando flood check",
    menuHint: "Type a number. Then Call.",
    langItem: "9 Language",
    langTitle: "Choose a language",
    back: "0 Back",
    ask: "Did the rule say this place flooded?",
    see: "See the numbers",
    yesTitle: "Yes.",
    noTitle: "No.",
    naTitle: "We could not look.",
    report: (name) => `${name} said this place flooded.`,
    yesBody: (seen, line, mm, rainLine) => [
      "A satellite saw open water",
      `on ${seen} of this place.`,
      `The line is ${line}.`,
      "",
      `Rain was ${mm} mm.`,
      `The line is ${rainLine} mm.`,
      "Both said yes.",
    ],
    noBody: (seen, line) => [
      "A satellite saw open water",
      `on ${seen} of this place.`,
      `The line is ${line}.`,
      "Rain was enough.",
      "Rain by itself does not pay.",
      "",
      "A news report said this place flooded.",
      "You can ask why the rule said no.",
    ],
    naBody: () => [
      "We had no map for this name.",
      "That does not mean it was dry.",
    ],
    amount: (eth) => `Practice amount for this place: ${eth} test ETH.`,
    notShillings: "Not shillings for one farmer.",
    notArrived: "It has not come. Ask the person holding this phone.",
    noMpesa: "SANDBOX. This demo sends no M-PESA.",
    notSeed: "Not money for seed. Water under a crop may not show.",
    house: (homes, kes) => `Together, a house guess (${homes}): ${kes}. Not one person's payment.`,
    noPay: "No payment from this check.",
    practice: "Practice message only.",
  },
  sw: {
    idleHint: "Simu ndogo",
    idleCode: "Angalia mafuriko",
    idleSub: "Bonyeza Piga",
    menuTitle: "Angalia mafuriko, Nyando",
    menuHint: "Andika namba. Kisha Piga.",
    langItem: "9 Lugha",
    langTitle: "Chagua lugha",
    back: "0 Rudi",
    ask: "Je, kanuni ilisema mahali hapa palifurika?",
    see: "Ona namba",
    yesTitle: "Ndiyo.",
    noTitle: "Hapana.",
    naTitle: "Hatukuweza kuangalia.",
    report: (name) => `${name} ilisema mahali hapa palifurika.`,
    yesBody: (seen, line, mm, rainLine) => [
      "Satelaiti iliona maji wazi",
      `kwenye ${seen} ya mahali hapa.`,
      `Mstari ni ${line}.`,
      "",
      `Mvua ilikuwa ${mm} mm.`,
      `Mstari ni ${rainLine} mm.`,
      "Zote mbili zilisema ndiyo.",
    ],
    noBody: (seen, line) => [
      "Satelaiti iliona maji wazi",
      `kwenye ${seen} ya mahali hapa.`,
      `Mstari ni ${line}.`,
      "Mvua ilitosha.",
      "Mvua peke yake hailipi.",
      "",
      "Ripoti ilisema mahali hapa palifurika.",
      "Unaweza kuuliza kwa nini kanuni ilisema hapana.",
    ],
    naBody: () => [
      "Hatuna ramani ya jina hili.",
      "Hii haimaanishi palikuwa pakavu.",
    ],
    amount: (eth) => `Kiasi cha mazoezi hapa: ${eth} test ETH.`,
    notShillings: "Si shilingi za mkulima mmoja.",
    notArrived: "Haijafika. Uliza aliye na simu hii.",
    noMpesa: "SANDBOX. Demo hii haitumi M-PESA.",
    notSeed: "Si pesa ya mbegu. Maji chini ya mmea hayaonekani.",
    house: (homes, kes) => `Pamoja, kesi ya nyumba (${homes}): ${kes}. Si malipo ya mtu mmoja.`,
    noPay: "Hakuna malipo kutoka ukaguzi huu.",
    practice: "Ujumbe wa mazoezi tu.",
  },
  luo: {
    idleHint: "Onge simu maduong'",
    idleCode: "Non pii",
    idleSub: "Di gocho",
    menuTitle: "Non pii, Nyando",
    menuHint: "Ndik namba. Eka gocho.",
    langItem: "9 Dhok",
    langTitle: "Yier dhok",
    back: "0 Chien",
    ask: "Be chik owacho ni kama ni nobiro pii?",
    see: "Ne namba",
    yesTitle: "Ee.",
    noTitle: "Dawe.",
    naTitle: "Ok wang'eyo.",
    report: (name) => `${name} owacho ni kama ni nobiro pii.`,
    yesBody: (seen, line, mm, rainLine) => [
      "Waneno pii.",
      `${seen} mar kama ni.`,
      `Line en ${line}.`,
      "",
      `Koth ne ${mm} mm.`,
      `Line en ${rainLine} mm.`,
      "Duto owacho ee.",
    ],
    noBody: (seen, line) => [
      `Pii en ${seen}.`,
      `Line en ${line}.`,
      "Koth oromo.",
      "Koth kendene ok chul.",
      "",
      "Ripot owacho ni kama ni nobiro pii.",
      "Inyalo penjo gima omiyo dawe.",
    ],
    naBody: () => [
      "Onge map mar nying ni.",
      "Ok en ni ne onge pii.",
    ],
    amount: (eth) => `Pesa mar temo kae: ${eth} test ETH.`,
    notShillings: "Ok en shilingi mar ng'ato achiel.",
    notArrived: "Pok obiro. Penjo ng'at man kod simu.",
    noMpesa: "SANDBOX. Onge M-PESA.",
    notSeed: "Ok en pesa mar cham. Pii e cham nyalo kik nenre.",
    house: (homes, kes) => `Kesi mar udi (${homes}): ${kes}. Ok en pesa mar ng'ato achiel.`,
    noPay: "Onge pesa mar nono ni.",
    practice: "Weche mag temo kende.",
  },
};

function phoneText() {
  return PHONE_COPY[phoneLang] || PHONE_COPY.en;
}

function phoneWeek() {
  const label = weekLabel();
  if (phoneLang === "sw") return label.replace("May", "Mei");
  return label;
}

function placeKind(place) {
  if (place.radar === "yes" && place.rain === "yes") return "yes";
  if (!place.box || place.radar === "abstain") return "na";
  return "no";
}

function homeWords(place) {
  const n = place.households;
  const more = /^more than /i.test(place.households_note || "");
  if (phoneLang === "sw") return more ? `zaidi ya nyumba ${n}` : `nyumba ${n}`;
  if (phoneLang === "luo") return more ? `udi mangeny, ${n}` : `udi ${n}`;
  return place.households_note || `${n} homes`;
}

function moneyLines(place, kind) {
  const copy = phoneText();
  const eth = cache?.loss?.grant_eth || "0.001";
  const kes = place.ground_up_label;
  const house = place.households && kes && kes !== "—" ? [copy.house(homeWords(place), kes)] : [];
  const shared = [copy.notArrived, copy.notSeed, ...house];
  if (kind === "yes") {
    return ["", copy.amount(eth), copy.notShillings, ...shared, copy.noMpesa, "", copy.practice, "SANDBOX"];
  }
  return ["", copy.noPay, ...shared];
}

function placeStory(place) {
  const copy = phoneText();
  const rain = cache?.rainfall || {};
  const line = pctLabel(cache?.radar?.line ?? 0.05) || "5%";
  const seen = pctLabel(place.fraction) || "—";
  const mm = rain.mm ?? "—";
  const rainLine = rain.line_mm ?? 40;
  const kind = placeKind(place);
  const head = kind === "yes"
    ? copy.yesBody(seen, line, mm, rainLine)
    : kind === "na"
      ? copy.naBody()
      : copy.noBody(seen, line);
  const cls = kind === "yes" ? "yes" : kind === "na" ? "na" : "no";
  const title = kind === "yes" ? copy.yesTitle : kind === "na" ? copy.naTitle : copy.noTitle;
  return { cls, title, lines: head.concat(moneyLines(place, kind)) };
}

function farmerCard(place) {
  const copy = phoneText();
  const story = placeStory(place);
  const source = place.label_url
    ? `<a href="${esc(place.label_url)}">${esc(copy.report(place.label_source || "A report"))}</a>`
    : "";
  const body = story.lines.filter((line) => line).map((line) => `<p>${esc(line)}</p>`).join("");
  return `<article class="farmer ${story.cls}" id="${esc(place.slug)}">
    <h2>${esc(place.name)}</h2>
    <p class="farmer-q">${esc(copy.ask)}</p>
    <p class="farmer-a">${esc(story.title)}</p>
    ${body}
    <p class="meta">${source} <a href="/claim/${esc(place.slug)}">${esc(copy.see)}</a></p>
  </article>`;
}

const PHONE_KEYS = [
  ["1", ""],
  ["2", "ABC"],
  ["3", "DEF"],
  ["4", "GHI"],
  ["5", "JKL"],
  ["6", "MNO"],
  ["7", "PQRS"],
  ["8", "TUV"],
  ["9", "WXYZ"],
  ["*", ""],
  ["0", "+"],
  ["#", ""],
];

function phonePad() {
  return PHONE_KEYS.map(([key, letters]) => {
    const sub = letters ? `<sub>${letters}</sub>` : "";
    return `<button type="button" data-phone-key="${key}">${key}${sub}</button>`;
  }).join("");
}

function phoneMenu(places) {
  const copy = phoneText();
  const lines = [copy.menuTitle, phoneWeek(), ""];
  places.forEach((place, index) => lines.push(`${index + 1} ${place.name}`));
  lines.push("", copy.langItem, "", copy.menuHint);
  return lines.join("\n");
}

function phoneLangScreen() {
  const copy = phoneText();
  return [copy.langTitle, "", "1 English", "2 Kiswahili", "3 Dholuo", "", copy.back].join("\n");
}

function phonePlace(place) {
  const story = placeStory(place);
  return [place.name, "", story.title, ...story.lines, "", phoneText().back].join("\n");
}

function phoneDetail() {
  const places = cache?.places || [];
  const place = places.find((item) => item.slug === phoneSlug);
  const langs = [
    ["en", "English"],
    ["sw", "Kiswahili"],
    ["luo", "Dholuo"],
  ].map(([id, label]) => `
    <button type="button" data-phone-lang="${id}" class="${phoneLang === id ? "on" : ""}">${label}</button>`).join("");
  const picks = places.map((item, index) => `
    <button type="button" data-phone-place="${esc(item.slug)}" class="${item.slug === phoneSlug ? "on" : ""}">${index + 1} ${esc(item.name)}</button>`).join("");
  const card = place
    ? farmerCard(place)
    : `<p class="note">Press Call, then a place number, then Call again. The screen is the short message. This card is the same message, with the news link.</p>`;
  const luoNote = phoneLang === "luo"
    ? `<p class="note">A Luo speaker has not checked these Dholuo lines.</p>`
    : "";
  return `<div class="phone-picks">${langs}</div><div class="phone-picks">${picks}</div>${card}${luoNote}`;
}

function paintPhone() {
  const idle = document.querySelector("[data-phone-idle]");
  const ussd = document.querySelector("[data-phone-ussd]");
  const text = document.querySelector("[data-phone-text]");
  const input = document.querySelector("[data-phone-input]");
  const detail = document.querySelector("[data-phone-detail]");
  const call = document.querySelector(".soft-call");
  if (!idle || !ussd || !text) return;
  const clock = document.querySelector("[data-phone-clock]");
  if (clock) {
    clock.textContent = new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  }
  const places = cache?.places || [];
  const copy = phoneText();
  const hint = document.querySelector(".idle-hint");
  const code = document.querySelector(".idle-code");
  const sub = document.querySelector(".idle-sub");
  if (hint) hint.textContent = copy.idleHint;
  if (code) code.textContent = copy.idleCode;
  if (sub) sub.textContent = copy.idleSub;
  idle.hidden = phoneMode !== "idle";
  ussd.hidden = phoneMode === "idle";
  if (phoneMode === "menu") text.textContent = phoneMenu(places);
  if (phoneMode === "lang") text.textContent = phoneLangScreen();
  if (phoneMode === "place") {
    const place = places.find((item) => item.slug === phoneSlug);
    text.textContent = place ? phonePlace(place) : copy.back;
    ussd.classList.toggle("is-sandbox", !!(place && place.radar === "yes" && place.rain === "yes"));
  } else {
    ussd.classList.remove("is-sandbox");
  }
  if (input) input.value = phoneBuffer;
  if (call) call.classList.toggle("is-waiting", phoneMode === "idle");
  if (detail) detail.innerHTML = phoneDetail();
}

function phoneKey(key) {
  if (phoneMode === "idle") return;
  if (!/^[0-9]$/.test(key)) return;
  phoneBuffer = key;
  paintPhone();
}

function phoneSubmit() {
  const places = cache?.places || [];
  const choice = phoneBuffer;
  if (phoneMode === "lang") {
    const next = { 1: "en", 2: "sw", 3: "luo" }[choice];
    if (next) phoneLang = next;
    if (next || choice === "0") {
      phoneMode = "menu";
      phoneBuffer = "";
    }
    paintPhone();
    return;
  }
  if (phoneMode === "menu" && choice === "9") {
    phoneMode = "lang";
    phoneBuffer = "";
    paintPhone();
    return;
  }
  const number = Number(choice);
  if (phoneMode === "menu" && number >= 1 && number <= places.length) {
    phoneMode = "place";
    phoneSlug = places[number - 1].slug;
    phoneBuffer = "";
  } else if ((phoneMode === "place" || phoneMode === "menu") && choice === "0") {
    phoneMode = "menu";
    phoneSlug = "";
    phoneBuffer = "";
  }
  paintPhone();
}

function phoneAction(action) {
  if (action === "call") {
    if (phoneMode === "idle") {
      phoneMode = "menu";
      phoneBuffer = "";
    } else {
      phoneSubmit();
      return;
    }
  } else if (action === "end") {
    phoneMode = "idle";
    phoneSlug = "";
    phoneBuffer = "";
  } else if (action === "clear") {
    if (phoneBuffer) phoneBuffer = "";
    else if (phoneMode === "place" || phoneMode === "lang") {
      phoneMode = "menu";
      phoneSlug = "";
    } else phoneMode = "idle";
  }
  paintPhone();
}

function openPhonePlace(slug) {
  phoneMode = "place";
  phoneSlug = slug;
  phoneBuffer = "";
  paintPhone();
}

function farmerDesk() {
  return shell("The reason — smallholders and pastoralists", `
    <section class="block tight farmer-head"><div class="wrap">
      <p class="eyebrow">${esc(weekLabel())} · Nyando · smallholders and pastoralists</p>
      <h1>A short message on a small phone.</h1>
      <p class="lede">An insurer or a responder holds this phone up. Farmers do not use this website. The screen says yes, no, or we could not look. If money were sent in this demo, the screen would say it is only a practice message. No money has been sent.</p>
      <div class="phone-stage">
        <div class="handset" role="group" aria-label="Feature phone">
          <div class="handset-ear"></div>
          <div class="handset-screen">
            <div class="handset-status">
              <span>Safaricom</span>
              <span data-phone-clock>12:00</span>
              <span aria-hidden="true">▍▍▌</span>
            </div>
            <div class="handset-lcd">
              <div data-phone-idle>
                <p class="idle-hint">No smartphone</p>
                <p class="idle-code">Flood check</p>
                <p class="idle-sub">Press Call</p>
              </div>
              <div class="ussd-box" data-phone-ussd hidden>
                <pre data-phone-text aria-live="polite"></pre>
                <input data-phone-input readonly aria-label="Number typed on the keypad" />
                <div class="ussd-actions">
                  <button type="button" data-phone="clear">CANCEL</button>
                  <button type="button" data-phone="call">SEND</button>
                </div>
              </div>
            </div>
          </div>
          <div class="handset-pad">${phonePad()}</div>
          <div class="handset-soft">
            <button type="button" class="soft-clear" data-phone="clear">Clear</button>
            <button type="button" class="soft-call" data-phone="call">Call</button>
            <button type="button" class="soft-end" data-phone="end">End</button>
          </div>
        </div>
        <aside class="phone-guide">
          <h2>What the phone says</h2>
          <ol>
            <li>Press <b>Call</b>.</li>
            <li>Press a place number, then <b>Call</b> again.</li>
            <li>Press <b>9</b> to change the language. <b>0</b> goes back. End returns to the start.</li>
          </ol>
          <div data-phone-detail></div>
          <p class="note" data-sandbox><b>SANDBOX.</b> This demo sends no M-PESA. No Daraja call. No shillings moved. If a testnet release happens, the record stays labelled SANDBOX.</p>
          <p class="note">On a yes, the practice amount is 0.001 test ETH for the whole place, from the committed table. It is not shillings for one farmer, and nothing has been sent. Where a news report named homes, the shilling figure is a house-damage guess for all of those homes together. It is not a payment, and not money for seed. Water under a crop may not show on the satellite. If nothing arrives, ask the person holding the phone.</p>
        </aside>
      </div>
    </div></section>
  `, "/desk/farmer");
}

function unknown() {
  return shell("Not found — Aetheris", `
    <section class="block"><div class="wrap">
      <h1>That page is not here.</h1>
      <p class="lede">Home, method, claims, backtest and the desks are on this app.</p>
      <a class="btn primary" href="/">Home</a>
    </section>
  `, "/");
}

function ctx() {
  return { cache, esc, shell, weekLabel };
}

function page() {
  const path = pathOf();
  if (path === "/") return landing();
  if (path === "/enter") return enterPage();
  if (path === "/desks") return desksPage();
  if (path === "/method") return methodPage(ctx());
  if (path === "/claims") return claimsPage(ctx());
  if (path === "/backtest") return backtestPage(ctx());
  if (path.startsWith("/claim/")) return placePage(ctx(), path.slice("/claim/".length));
  if (path === "/desk/data") return dataDesk();
  if (path === "/desk/insurer") return insurerDesk();
  if (path === "/desk/reinsurer") return reinsurerDesk();
  if (path === "/desk/responder") return responderDesk();
  if (path === "/desk/research") return researchDesk();
  if (path === "/desk/farmer") return farmerDesk();
  return unknown();
}

function bind() {
  document.body.addEventListener("change", (ev) => {
    const box = ev.target.closest("[data-confirm-challenge]");
    if (!box) return;
    const btn = document.querySelector("[data-act='challenge']");
    if (btn) btn.disabled = !box.checked;
  });
  document.body.addEventListener("click", async (ev) => {
    const walletBtn = ev.target.closest("[data-wallet]");
    if (walletBtn) {
      ev.preventDefault();
      await onWalletClick();
      return;
    }
    const actBtn = ev.target.closest("[data-act]");
    if (actBtn) {
      ev.preventDefault();
      const slug = pathOf().startsWith("/claim/") ? pathOf().slice("/claim/".length) : "kabonyo-kanyagwal";
      await onAct(actBtn.dataset.act, slug);
      return;
    }
    const themeBtn = ev.target.closest("button[data-theme]");
    if (themeBtn) {
      setTheme(theme === "dark" ? "light" : "dark");
      render();
      return;
    }
    const leaveBtn = ev.target.closest("[data-leave]");
    if (leaveBtn) {
      ev.preventDefault();
      await leave();
      viewer = null;
      go("/");
      return;
    }
    const langBtn = ev.target.closest("[data-phone-lang]");
    if (langBtn && pathOf() === "/desk/farmer") {
      phoneLang = langBtn.dataset.phoneLang;
      paintPhone();
      return;
    }
    const phonePlaceBtn = ev.target.closest("[data-phone-place]");
    if (phonePlaceBtn && pathOf() === "/desk/farmer") {
      openPhonePlace(phonePlaceBtn.dataset.phonePlace);
      return;
    }
    const phoneKeyBtn = ev.target.closest("[data-phone-key]");
    if (phoneKeyBtn && pathOf() === "/desk/farmer") {
      phoneKey(phoneKeyBtn.dataset.phoneKey);
      return;
    }
    const phoneBtn = ev.target.closest("[data-phone]");
    if (phoneBtn && pathOf() === "/desk/farmer") {
      phoneAction(phoneBtn.dataset.phone);
      return;
    }
    const pick = ev.target.closest("[data-slug]");
    if (pick) {
      if (pathOf() === "/desk/responder") showResponder(pick.dataset.slug);
      else showPlace(pick.dataset.slug);
      return;
    }
    const a = ev.target.closest("a");
    if (!a) return;
    const href = a.getAttribute("href");
    if (!href || href.startsWith("http") || href.startsWith("/data/")) return;
    if (href.startsWith("/desk/")) return;
    ev.preventDefault();
    go(href);
  });
  document.body.addEventListener("keydown", (ev) => {
    if (pathOf() !== "/desk/farmer") return;
    if (/^[0-9]$/.test(ev.key)) {
      ev.preventDefault();
      phoneKey(ev.key);
    } else if (ev.key === "Enter") {
      ev.preventDefault();
      phoneAction("call");
    } else if (ev.key === "Backspace") {
      ev.preventDefault();
      phoneAction("clear");
    } else if (ev.key === "Escape") {
      ev.preventDefault();
      phoneAction("end");
    }
  });
}

async function render() {
  const raw = location.pathname.replace(/\/$/, "") || "/";
  const clean = normalizePath(raw);
  if (clean !== raw) history.replaceState({}, "", clean);
  const root = document.getElementById("app");
  theme = themeNow();
  document.documentElement.setAttribute("data-theme", theme);
  if (!cache) {
    root.innerHTML = shell("Aetheris", `<section class="block"><div class="wrap"><p>Loading the week from the files…</p></div></section>`, pathOf());
    try {
      await load();
    } catch {
      root.innerHTML = shell("Aetheris", `<section class="block"><div class="wrap"><h1>The local API is not running.</h1><p class="lede">Start it with <code>python web/server.py</code> then refresh.</p></div></section>`, pathOf());
      return;
    }
  }
  try {
    root.innerHTML = page();
  } catch (err) {
    root.innerHTML = `<div class="block"><div class="wrap"><h1>The page failed to open.</h1><p class="lede">${esc(err.message)}</p></div></div>`;
    return;
  }
  const places = cache?.places || [];
  const onResponder = pathOf() === "/desk/responder";
  const first = onResponder
    ? places.find((p) => actionOf(p).id === "go") || places[0]
    : places[0];
  if (first) {
    if (onResponder) showResponder(first.slug);
    else showPlace(first.slug);
  }
  if (pathOf() === "/desk/farmer") paintPhone();
  if (document.getElementById("kenya-map")) {
    const drawn = onResponder ? places.map((p) => ({ ...p, tone: actionOf(p).id })) : places;
    const pick = onResponder ? showResponder : showPlace;
    requestAnimationFrame(() => {
      mountKenyaMap(drawn, pick);
      if (first?.zone) focusBox(first.slug);
    });
  }
  paintWalletButton();
  afterPage(pathOf()).catch(() => {});
}

bind();
window.addEventListener("popstate", () => render());
render();
