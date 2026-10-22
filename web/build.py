"""Build web/index.html from the repo's own evidence.

Run:  python web/build.py

Why a generator and not hand-typed HTML: every number on the page comes from
the same files the backtest reads, so the page cannot drift from the result.
  config/rule.yaml                  thresholds, rule id, thresholdsHash
  labels/label_log.csv              which places reports named, and from where
  backtest/labels.csv               the scale notes for each label
  backtest/checks/radar_fractions.csv   measured radar fractions and pixel counts
  backtest/observations.csv         what each source signed
  backtest/results/counts.csv       counts written by backtest/score.py
  web/data/deployment.json          optional; written by contracts/deploy_testnet.mjs

Assumption: the page is static. The only script is a countdown that improves a
time already printed in plain text, so it works with scripting off.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.pipeline.rainfall import published_total  # noqa: E402
from backtest.pipeline.report import PUBLISHED_ITEM  # noqa: E402
from backtest.pipeline.rule import load_rule, rule_id, thresholds_hash  # noqa: E402

OUT = ROOT / "web" / "index.html"
DEPLOYMENT = ROOT / "web" / "data" / "deployment.json"
REPO = "https://github.com/Nosh-thee-techy/aetheris"

# Display names and the scale each name was reported at. The scale is shown
# beside the name because a ward box and a dispensary are not the same claim.
PLACES = {
    "ahero": ("Ahero", "Town, 3 km box around the town point"),
    "kabonyo-kanyagwal": ("Kabonyo Kanyagwal", "Ward"),
    "kakola-ombaka": ("Kakola Ombaka", "Named area, no outline found"),
    "nyamasao": ("Nyamasao", "Dispensary, no outline found"),
    "ombeyi": ("Ombeyi", "Location, measured on the ward box"),
    "kobura": ("Kobura", "Ward box; the report said village"),
    "kadibo": ("Kadibo", "Sub-county, no outline found"),
}


def read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def num(text: str) -> int | None:
    return int(text) if text not in ("", None) else None


def load_places() -> list[dict]:
    """Join the radar rows, the rainfall rows, and the label log by zone."""
    radar = {row["zone_id"]: row for row in read(ROOT / "backtest" / "checks" / "radar_fractions.csv")}
    notes = {row["zone_id"]: row for row in read(ROOT / "backtest" / "labels.csv")}
    logged = {row["zone"]: row for row in read(ROOT / "labels" / "label_log.csv")}
    rain = {
        row["zone_id"]: row
        for row in read(ROOT / "backtest" / "observations.csv")
        if row["source"] == "rainfall"
    }
    places = []
    for slug, (name, scale) in PLACES.items():
        r = radar[slug]
        fraction = float(r["flooded_fraction"]) if r["flooded_fraction"] else None
        valid, land, flooded = num(r["valid_pixels"]), num(r["land_pixels"]), num(r["flooded_pixels"])
        places.append(
            {
                "slug": slug,
                "name": name,
                "scale": scale,
                "fraction": fraction,
                "decision": r["decision"],
                "reason": r["reason"],
                "land": land,
                "flooded": flooded,
                "removed": (valid - land) if valid is not None and land is not None else None,
                "rain": rain[slug]["decision"],
                "label_source": logged[slug]["source"],
                "label_url": logged[slug]["source_url"],
                "label_note": notes[slug]["notes"],
                "box_note": r["scale"],
            }
        )
    # Measured places first, strongest radar signal first. Places we could not
    # assess go last so the empty bars do not read as small values.
    places.sort(key=lambda p: (p["fraction"] is None, -(p["fraction"] or 0)))
    return places


def verdict(place: dict) -> tuple[str, str, str]:
    """(marker class, short outcome, plain reason) for one place."""
    line = pct(RADAR_LINE)
    if place["decision"] == "abstain":
        return (
            "na",
            "Cannot assess",
            "No outline we could trust was found for this named place. The geocoders returned other "
            "places with similar names, and we did not measure those. Radar was not run here. "
            "This is not a missing satellite pass: the 6 May scene exists.",
        )
    if place["decision"] == "yes" and place["rain"] == "yes":
        return (
            "signed",
            "Claim opens",
            f"Radar found open water on {pct(place['fraction'])} of land pixels, above the {line} line, "
            "and the rainfall catchment also signed. Both signatures would open the 24-hour challenge window.",
        )
    return (
        "no",
        "No claim opens",
        f"Radar found open water on {pct(place['fraction'])} of land pixels, below the {line} line, so radar "
        "did not sign. Rainfall signed, but rainfall alone cannot open a claim. A report says this place "
        "flooded, so under this rule it is a miss. Radar sees open water only: flooding under crops, trees "
        "or buildings is invisible to it.",
    )


def render_board(places: list[dict]) -> str:
    scale_max = 0.10  # bar scale: 10 % of land pixels; the line sits at 5 %.
    rows = []
    for p in places:
        marker, outcome, why = verdict(p)
        if p["fraction"] is None:
            bar = '<div class="hatch" role="img" aria-label="No radar measurement">no outline, not measured</div>'
            radar_signs = '<span class="sig"><span class="dot na"></span>Not assessed</span>'
        else:
            width = min(p["fraction"] / scale_max, 1.0) * 100
            line_at = RADAR_LINE / scale_max * 100
            bar = (
                f'<div class="gauge" role="img" aria-label="Open water on {pct(p["fraction"])} of land pixels; '
                f'line at {pct(RADAR_LINE)}"><i class="radar" style="width:{width:.1f}%"></i>'
                f'<b style="left:{line_at:.1f}%"></b></div>'
                f'<span class="pct">{pct(p["fraction"])} of land pixels</span>'
            )
            dot = "signed" if p["decision"] == "yes" else "no"
            word = "Signed" if p["decision"] == "yes" else "Did not sign"
            radar_signs = f'<span class="sig"><span class="dot {dot}"></span>{word}</span>'
        rain_signs = (
            '<span class="sig"><span class="dot signed"></span>Signed</span>'
            if p["rain"] == "yes"
            else '<span class="sig"><span class="dot no"></span>Did not sign</span>'
        )
        evidence = [
            ("Radar scene", PUBLISHED_ITEM),
            ("Water test", f"VV below {RULE['radar']['threshold_db']:g} dB, land pixels only"),
        ]
        if p["land"] is not None:
            evidence += [
                ("Land pixels read", f"{p['land']:,}"),
                ("Looked like water", f"{p['flooded']:,}"),
                ("Permanent water removed", f"{p['removed']:,} pixels (JRC occurrence ≥ {RULE['radar']['permanent_water_occurrence']})"),
            ]
        evidence.append(("Area measured", p["box_note"]))
        dl = "".join(f"<dt>{escape(k)}</dt><dd>{escape(v)}</dd>" for k, v in evidence)
        rows.append(
            f"""<details class="place">
  <summary>
    <div><span class="name">{escape(p['name'])}</span><span class="scale">{escape(p['scale'])}</span></div>
    <div><span class="cell-label">Radar</span>{bar}</div>
    <div><span class="cell-label">Rainfall</span>{rain_signs}</div>
    <div><span class="cell-label">Outcome</span><span class="out"><span class="dot {marker}"></span>{escape(outcome)}</span> <span class="caret" aria-hidden="true">+</span></div>
  </summary>
  <div class="evidence">
    <div>
      <h4>Radar</h4>
      <p>{radar_signs}</p>
      <dl>{dl}</dl>
    </div>
    <div>
      <h4>Why this place was counted as flooded</h4>
      <p>{escape(p['label_note'])}</p>
      <p><a href="{escape(p['label_url'])}">{escape(p['label_source'])}</a>, reported 4–5 May 2024. A news report is a label, not a survey.</p>
    </div>
    <p class="why"><b>The reason for this decision.</b> {escape(why)}</p>
  </div>
</details>"""
        )
    return "\n".join(rows)


def render_matrix(places: list[dict], counts: dict) -> str:
    def names(pred) -> str:
        found = [p["name"] for p in places if pred(p)]
        return ", ".join(found)

    cells = {
        ("yes", "yes"): [p for p in places if p["decision"] == "yes" and p["rain"] == "yes"],
        ("no", "yes"): [p for p in places if p["decision"] == "no" and p["rain"] == "yes"],
        ("abstain", "yes"): [p for p in places if p["decision"] == "abstain" and p["rain"] == "yes"],
    }

    def cell(key, highlight=False, label=""):
        group = cells[key]
        if not group:
            return '<td class="zero n">0</td>'
        cls = ' class="hl"' if highlight else ""
        return f'<td{cls}><span class="big">{len(group)}</span><small>{escape(", ".join(p["name"] for p in group))}</small></td>'

    zero = '<td class="zero n">0</td>'
    return f"""<table class="matrix">
  <caption>Radar (rows) against rainfall (columns), 7 places reported flooded</caption>
  <thead><tr><th></th><th scope="col">Rainfall signed</th><th scope="col">Rainfall did not sign</th></tr></thead>
  <tbody>
    <tr><th scope="row">Radar signed</th>{cell(("yes", "yes"))}{zero}</tr>
    <tr><th scope="row">Radar did not sign</th>{cell(("no", "yes"), True)}{zero}</tr>
    <tr><th scope="row">Radar not assessed</th>{cell(("abstain", "yes"))}{zero}</tr>
  </tbody>
</table>"""


def render_rules(counts: dict) -> str:
    labels = {"radar_only": "Radar only", "radar_plus_rainfall": "Radar and rainfall (the rule)", "rainfall_only": "Rainfall only"}
    rows = "".join(
        f'<tr><th scope="row">{labels[name]}</th><td class="n">{v["hits"]}</td><td class="n">{v["misses"]}</td><td class="n">{v["false"]}</td></tr>'
        for name, v in counts["rules"].items()
    )
    return f"""<table>
  <caption>Three rules on the same seven places</caption>
  <thead><tr><th></th><th class="n">Found</th><th class="n">Missed</th><th class="n">False triggers</th></tr></thead>
  <tbody>{rows}</tbody>
</table>"""


def load_counts() -> dict:
    rules: dict[str, dict[str, int]] = {}
    agreement: dict[str, int] = {}
    misses: dict[str, int] = {}
    for row in read(ROOT / "backtest" / "results" / "counts.csv"):
        if row["table"] == "rule":
            rules[row["name"]] = {"hits": int(row["hits"]), "misses": int(row["misses"]), "false": int(row["false_triggers"])}
        elif row["table"] == "agreement":
            agreement[row["name"]] = int(row["count"])
        elif row["table"] == "miss":
            misses[row["name"]] = int(row["count"])
    return {"rules": rules, "agreement": agreement, "misses": misses}


def short(address: str) -> str:
    return f"{address[:8]}…{address[-6:]}"


def render_chain(deployment: dict | None) -> str:
    constants = f"""<dl>
      <dt>Attester bond</dt><dd>0.01 ETH, returned when a claim finalizes</dd>
      <dt>Challenge stake</dt><dd>0.01 ETH</dd>
      <dt>Challenge window</dt><dd>24 hours after both signatures</dd>
      <dt>Referee window</dt><dd>48 hours, then the attesters’ claim stands</dd>
      <dt>Rule id</dt><dd>{escape(RULE['rule_id'])}<br><code>0x{RULE_ID.hex()}</code></dd>
      <dt>Thresholds hash</dt><dd><code>0x{THRESHOLDS.hex()}</code></dd>
    </dl>"""
    if not deployment:
        return f"""<div class="chain">
  <div class="panel">
    <span class="status wait">Not deployed yet</span>
    <h3>Testnet deployment</h3>
    <p>The contracts are written and their tests run in CI, but nothing from this project is on a public
    testnet yet. Deploying needs a little test ETH in the project’s own test wallets, which has to come from a
    faucet. Until that happens this page shows no on-chain state, because inventing some would be the opposite
    of what it is for.</p>
    <p class="note">When deployed, this section lists each contract, each signer, each signature’s evidence
    hash, a live challenge countdown, and the escrow’s pool.</p>
  </div>
  <div class="panel">
    <h3>What is fixed when it is deployed</h3>
    {constants}
  </div>
</div>"""

    explorer = deployment["explorer"]

    def link(addr: str, kind: str = "address") -> str:
        return f'<a href="{explorer}/{kind}/{escape(addr)}"><code>{escape(short(addr))}</code></a>'

    roles = "".join(
        f"<dt>{escape(label)}</dt><dd>{link(deployment['roles'][key])}</dd>"
        for key, label in [("radar", "Radar attester"), ("rainfall", "Rainfall attester"), ("resolver", "Referee (one key in this demo)"), ("funder", "Funder"), ("pool", "Slash pool")]
    )
    claims_html = ""
    for claim in deployment.get("claims", []):
        signers = "".join(
            f"<li class='done'><b>{escape(s['role'])}</b> signed · evidence <code>{escape(s['evidence'][:14])}…</code></li>"
            for s in claim["signers"]
        )
        finalizes = claim.get("finalizes_at")
        when = (
            datetime.fromtimestamp(finalizes, tz=timezone.utc).strftime("%d %b %Y %H:%M UTC")
            if finalizes
            else "after both signatures"
        )
        claims_html += f"""<div class="panel">
    <span class="status live">{escape(claim['state'])}</span>
    <h3>Claim: {escape(claim['zone_name'])}, 4–6 May 2024</h3>
    <div class="countdown" data-finalizes="{finalizes or ''}">{escape(when)}</div>
    <p class="note">Anyone can stake a challenge until then. After it, anyone can finalize and the escrow can release once.</p>
    <ul class="tl">{signers}<li>Challenge window closes {escape(when)}</li><li>Finalize, then the escrow can release once</li></ul>
    <dl><dt>Claim id</dt><dd><code>{escape(claim['trigger_id'])}</code></dd></dl>
  </div>"""
    return f"""<div class="chain">
  <div class="panel">
    <span class="status live">Deployed on {escape(deployment['network'])}</span>
    <h3>Contracts</h3>
    <dl>
      <dt>FloodTrigger</dt><dd>{link(deployment['trigger']['address'])}</dd>
      <dt>PayoutEscrow</dt><dd>{link(deployment['escrow']['address'])}</dd>
      <dt>Block</dt><dd>{deployment['block']}</dd>
      <dt>Policy hash</dt><dd><code>{escape(deployment['policy_hash'])}</code></dd>
      <dt>Escrow pool</dt><dd>{escape(str(deployment['pool_balance_eth']))} test ETH</dd>
      <dt>Snapshot</dt><dd>{escape(deployment['snapshot_at'])}</dd>
    </dl>
  </div>
  <div class="panel"><h3>Roles</h3><dl>{roles}</dl></div>
  {claims_html}
  <div class="panel"><h3>Fixed at deploy</h3>{constants}</div>
</div>"""


def build() -> str:
    places = load_places()
    counts = load_counts()
    deployment = json.loads(DEPLOYMENT.read_text(encoding="utf-8")) if DEPLOYMENT.exists() else None
    rain_mm = published_total()
    n = len(places)
    rain_signed = sum(1 for p in places if p["rain"] == "yes")
    radar_signed = sum(1 for p in places if p["decision"] == "yes")
    radar_no = sum(1 for p in places if p["decision"] == "no")
    unassessed = sum(1 for p in places if p["decision"] == "abstain")
    rain_line = RULE["rainfall"]["threshold_mm"]
    rain_scale = 80.0
    built = datetime.now(timezone.utc).strftime("%d %b %Y")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aetheris — a verification layer for flood data in Kenya</title>
<meta name="description" content="Aetheris cross-checks satellite rainfall against Sentinel-1 radar, place by place and week by week, and records the result on a testnet where anyone can check or challenge it.">
<link rel="stylesheet" href="styles.css">
</head>
<body>
<a class="skip" href="#main">Skip to the evidence</a>
<div class="band" role="note"><div class="wrap"><span><b>Testnet only.</b> Nothing here moves real money.</span><span><b>M-PESA is a sandbox.</b></span><span>Unaudited contracts.</span></div></div>

<header class="mast"><div class="wrap">
  <a class="mark" href="#top">Aether<span>is</span></a>
  <nav class="nav" aria-label="Sections">
    <a href="#why">Why</a><a href="#how">How a claim is accepted</a><a href="#week">One flood week</a><a href="#agree">Agreement</a><a href="#chain">On-chain</a><a href="#limits">Limits</a>
  </nav>
</div></header>

<main id="main">
<section class="hero" id="top"><div class="wrap">
  <p class="eyebrow">Verification layer · flood data · Kenya</p>
  <h1>Rain data said “flood” in {WORDS.get(n, n)} places. <em>Radar could confirm {WORDS.get(radar_signed, radar_signed)}.</em></h1>
  <p class="lede">Flood payouts and alerts rest on satellite rainfall estimates that are sparse on the ground and often wrong in heavy rain.
  <strong>Aetheris checks them against Sentinel-1 radar</strong>, which sees whether land is actually under water, for each place and week, and
  records the result where anyone can check it or challenge it. This is the first week we checked: the Nyando basin, 4–6 May 2024.</p>
  <div class="facts">
    <div class="fact"><span class="n">{n}</span><span class="k">places that news reports said flooded</span></div>
    <div class="fact"><span class="n rain">{rain_signed}</span><span class="k">where rainfall data signed “flood”</span></div>
    <div class="fact"><span class="n radar">{radar_signed}</span><span class="k">where radar also signed, so a claim would open. {radar_no} radar said no; {unassessed} could not be assessed.</span></div>
  </div>
</div></section>

<section class="block" id="why"><div class="wrap">
  <div class="sec-head"><span class="num">01</span><h2>When the data misses the flood, nobody can see why</h2>
  <p>Smallholder farmers and pastoralists in flood-prone basins are paid by weather-index insurance, or helped by alerts, only when the data says a flood happened.
  When that data misses their flood they get nothing, and the decision was made by a single operator, from an estimate, with no reason attached.</p></div>
  <p class="note">Aetheris attaches the reason. Each decision shows what each source measured, against which line, and who signed. It also counts how often the
  data misses real floods, so triggers can be designed more fairly over time. Today the benefit to farmers is indirect, and every payout in this demo is on a testnet or a sandbox.</p>
</div></section>

<section class="block alt" id="how"><div class="wrap">
  <div class="sec-head"><span class="num">02</span><h2>A flood is accepted only when radar and a second source both sign</h2>
  <p>Each place and week is one claim. Signing means “this payout rule fired”, not “I saw something”. Silence counts as no.</p></div>
  <ol class="steps">
    <li><span class="who radar">Radar</span><h3>Radar signs</h3><p>Sentinel-1 shows open water on enough of the place’s land, with permanent water removed. Required. Without it nothing opens.</p></li>
    <li><span class="who rain">Rainfall</span><h3>A second source signs</h3><p>Rain over the upstream catchment crosses the line. Rainfall alone can never open a claim. Each signer posts a 0.01 ETH bond and its own evidence hash.</p></li>
    <li><span class="who ink">Anyone</span><h3>Anyone can challenge</h3><p>For 24 hours, anyone can stake 0.01 ETH against the claim. A challenge freezes it. The referee can only uphold or reject.</p></li>
    <li><span class="who ink">Contract</span><h3>It finalizes</h3><p>If no one challenged, or the referee stayed silent for 48 hours, the claim stands. Bonds come back. A rejected claim slashes the bonds to the challenger.</p></li>
    <li><span class="who ink">Escrow</span><h3>It pays once</h3><p>Only a finalized claim releases funds, only to beneficiaries committed before the season, and each place-week-rule can be paid at most once.</p></li>
  </ol>
  <div class="rule-line"><p><b>The rule is frozen.</b> Radar line: open water below {RULE['radar']['threshold_db']:g} dB on at least {pct(RADAR_LINE)} of land pixels. Rainfall line: {rain_line} mm over three days on the upstream catchment, lag {RULE['rainfall']['lag_days']} days. Fixed on {escape(str(RULE['frozen_on']))}, before this week was scored, and hashed into every claim id. These are untuned starting values, not fitted to this flood.</p></div>
</div></section>

<section class="block" id="week"><div class="wrap">
  <div class="sec-head"><span class="num">03</span><h2>One flood week, place by place</h2>
  <p>Seven places that named news reports said flooded on 4–6 May 2024. Open any row to see what was measured and why the place was counted.</p></div>
  <ul class="legend" aria-label="Key">
    <li><span class="dot signed"></span>Signed</li><li><span class="dot no"></span>Did not sign</li><li><span class="dot na"></span>Could not assess</li>
    <li><span class="sw radar"></span>Radar: share of land that looks like open water</li><li><span class="sw line"></span>The rule’s line</li>
  </ul>
  <div class="catch">
    <div><b>Rainfall, for every place at once.</b> It is read on the upstream headwaters, not on each place, so it gives one answer for the whole week.</div>
    <div class="row">
      <div><div class="gauge" role="img" aria-label="{rain_mm:.1f} millimetres against a line at {rain_line} millimetres"><i class="rain" style="width:{rain_mm / rain_scale * 100:.1f}%"></i><b style="left:{rain_line / rain_scale * 100:.1f}%"></b></div>
      <div class="gauge-scale"><span>0 mm</span><span>line {rain_line} mm</span><span>{rain_scale:g} mm</span></div></div>
      <div><b>{rain_mm:.1f} mm</b> in the three days to 6 May (CHIRPS satellite estimate). Signed for all {n} places.</div>
    </div>
  </div>
  <div class="board-head" aria-hidden="true"><div>Place</div><div>Radar</div><div>Rainfall</div><div>Outcome</div></div>
  <div class="board">
{render_board(places)}
  </div>
  <p class="note">Boxes are working extents from OpenStreetMap, not surveyed flood outlines. {unassessed} places were left unassessed rather than measured at the wrong location.</p>
</div></section>

<section class="block alt" id="agree"><div class="wrap">
  <div class="sec-head"><span class="num">04</span><h2>Where the two sources agreed, disagreed, and what was missed</h2>
  <p>The rows where they disagree are the only rows where the second source changes the result.</p></div>
  <div class="matrix-wrap">
    <div>{render_matrix(places, counts)}</div>
    <div>{render_rules(counts)}</div>
  </div>
  <div class="takeaway">
    <p><b>Rainfall was “yes” in every place, so it told us almost nothing about which places flooded.</b> It disagreed with radar in {radar_no} of the {radar_signed + radar_no} places radar could judge.</p>
    <p>Requiring radar means {counts['rules']['radar_plus_rainfall']['misses']} of {n} reported floods produced no claim: {radar_no} where radar saw too little open water, and {unassessed} where it could not look. Rainfall alone would have found all {n}, but there is no “did not flood” place in this log, so we cannot say how often rainfall alone would raise a false alarm. Neither number is an accuracy figure. They are counts from one week.</p>
    <p>Misses caused by radar having no pass that week: <b>{counts['misses']['no_scene']}</b>. The 6 May scene existed.</p>
  </div>
</div></section>

<section class="block" id="chain"><div class="wrap">
  <div class="sec-head"><span class="num">05</span><h2>What is on the testnet</h2>
  <p>A contract holds a payout pool and releases it only for a finalized claim, to beneficiaries committed in advance, at most once per claim.</p></div>
  {render_chain(deployment)}
</div></section>

<section class="block alt" id="limits"><div class="wrap">
  <div class="sec-head"><span class="num">06</span><h2>What we are not claiming</h2>
  <p>This is not ground-truth validation, and it does not fix flood insurance.</p></div>
  <ul class="limits">
    <li><b>Radar has blind spots.</b><span>It sees open water. It does not see flood under crops, trees or buildings, and Sentinel-1’s 2024 revisit is twelve days, so a flood can rise and fall between passes.</span></li>
    <li><b>The sources overlap.</b><span>Rainfall and radar describe the same storm. Two signatures are not two independent witnesses, and the agreement table is how we show how much they add.</span></li>
    <li><b>Satellite rainfall is an estimate.</b><span>CHIRPS tends to overestimate light rain and underestimate heavy rain. Gauges are scarce here. IMERG is not connected.</span></li>
    <li><b>The referee is one key.</b><span>In this demo a single named key can uphold or reject a challenge. A committee, then a vote, is the intended path. The contract has one function for it, so swapping does not change the rest.</span></li>
    <li><b>One season, seven news reports.</b><span>Counts here are indicative. Reports favour places that reporters and rescuers could reach. There are no “did not flood” labels yet.</span></li>
    <li><b>Payouts are not real.</b><span>The escrow holds testnet ETH. M-PESA is a Daraja sandbox mirror that moves no money. The contracts are unaudited.</span></li>
  </ul>
</div></section>

<section class="block" id="users"><div class="wrap">
  <div class="sec-head"><span class="num">07</span><h2>Who this is for</h2></div>
  <span class="flag">Working assumptions. Not yet validated with users.</span>
  <div class="users">
    <div class="user"><h3>Insurers and aggregators</h3><p>They set and defend flood triggers and carry the cost of disputes. A checkable record of what each source said, and how often triggers miss, is something they can argue from.</p></div>
    <div class="user"><h3>County teams and humanitarian agencies</h3><p>A second signal, from a different instrument, before funds or alerts go out.</p></div>
    <div class="user"><h3>ICPAC, Kenya Met and researchers</h3><p>An open, repeatable check on how reliable satellite rainfall is where gauges are scarce.</p></div>
    <div class="user"><h3>Smallholder farmers and pastoralists</h3><p>The people most affected. The benefit to them today is indirect: a visible reason for each decision, and a measure of how often the data misses.</p></div>
  </div>
</div></section>
</main>

<footer><div class="wrap">
  <div><h3>Check it yourself</h3><ul>
    <li><a href="{REPO}/blob/main/docs/agreement.md">Agreement table, with pixel counts</a></li>
    <li><a href="{REPO}/blob/main/config/rule.yaml">The frozen rule</a></li>
    <li><a href="{REPO}/blob/main/labels/label_log.csv">Label log and sources</a></li>
    <li><a href="{REPO}">Source code</a></li>
  </ul></div>
  <div><h3>Data</h3><ul>
    <li>Sentinel-1 RTC via Microsoft Planetary Computer</li>
    <li>CHIRPS 2.0 daily rainfall</li>
    <li>JRC Global Surface Water</li>
    <li>Place boundaries © OpenStreetMap contributors</li>
  </ul></div>
  <div><h3>This page</h3><p>Generated {built} from the repository’s own files by <code>web/build.py</code>. IEEE ClimateChain Global Hackathon 2026, Climate Data &amp; Environmental Monitoring.</p></div>
</div></footer>

<script>
/* Progressive enhancement: turn a printed time into a live countdown. */
document.querySelectorAll('[data-finalizes]').forEach(function (el) {{
  var end = Number(el.getAttribute('data-finalizes'));
  if (!end) return;
  var plain = el.textContent;
  function tick() {{
    var left = end - Math.floor(Date.now() / 1000);
    if (left <= 0) {{ el.textContent = 'Window closed'; return; }}
    var h = Math.floor(left / 3600), m = Math.floor((left % 3600) / 60), s = left % 60;
    el.textContent = h + 'h ' + String(m).padStart(2, '0') + 'm ' + String(s).padStart(2, '0') + 's left';
    el.setAttribute('title', plain);
    setTimeout(tick, 1000);
  }}
  tick();
}});
</script>
</body>
</html>
"""


WORDS = {0: "none", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}
RULE = load_rule()
RADAR_LINE = float(RULE["radar"]["min_flooded_fraction"])
RULE_ID = rule_id()
THRESHOLDS = thresholds_hash()

if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT}")
