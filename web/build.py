"""Build the Aetheris site into web/.

Run:  python web/build.py

Pages written
  index.html            what this is, who it is for, how it is built, what it does not claim
  claims.html           the seven places for the flood week, with live testnet state
  claim-<place>.html    one page per place: evidence, signatures, timeline, actions
  backtest.html         agreement counts, rule check, downloads, how to reproduce
  payouts.html          the escrow, the committed table, the sandbox mirror
  chain-config.js       addresses, ids and the rule file, read by app.js
  data/                 copies of the files the numbers come from

Why a generator and not hand-typed HTML: every number comes from the files the
backtest reads, so the pages cannot drift from the result.
  config/rule.yaml                  thresholds, rule id, thresholdsHash
  labels/label_log.csv              which places reports named, and from where
  backtest/labels.csv               the scale notes for each label
  backtest/checks/radar_fractions.csv   measured radar fractions and pixel counts
  backtest/observations.csv         what each source signed
  backtest/results/counts.csv       counts written by backtest/score.py
  web/data/deployment.json          written by contracts/tools/deploy_testnet.mjs

Honesty rule: this script never writes chain state it did not read. The ids and
hashes it computes are checked against deployment.json, and the build fails if
they disagree. Live state comes from app.js reading the chain in the browser.
"""

from __future__ import annotations

import base64
import csv
import json
import shutil
import sys
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.pipeline.ids import CHIRPS, event_week, evidence_radar, evidence_rainfall, trigger_id, zone_id  # noqa: E402
from backtest.pipeline.rainfall import published_total  # noqa: E402
from backtest.pipeline.report import PUBLISHED_ITEM  # noqa: E402
from backtest.pipeline.rule import load_rule, rule_id, thresholds_hash  # noqa: E402

WEB = ROOT / "web"
DEPLOYMENT = WEB / "data" / "deployment.json"
REPO = "https://github.com/Nosh-thee-techy/aetheris"
RPCS = ["https://ethereum-sepolia-rpc.publicnode.com", "https://sepolia.drpc.org"]

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
WORDS = {0: "none", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}

RULE = load_rule()
RADAR_LINE = float(RULE["radar"]["min_flooded_fraction"])
RULE_ID = rule_id()
THRESHOLDS = thresholds_hash()
WEEK = RULE["event_weeks"][0]
WEEK_TEXT = "4–6 May 2024"
# These two windows are constants in FloodTrigger.sol.
CHALLENGE_WINDOW = 24 * 3600
RESOLVE_WINDOW = 48 * 3600


# ----------------------------------------------------------------------------
# data


def read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def num(text: str) -> int | None:
    return int(text) if text not in ("", None) else None


def hexed(raw: bytes) -> str:
    return "0x" + raw.hex()


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
                "page": f"claim-{slug}.html",
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
            "and the rainfall catchment also signed. Both signatures open the 24-hour challenge window.",
        )
    return (
        "no",
        "No claim opens",
        f"Radar found open water on {pct(place['fraction'])} of land pixels, below the {line} line, so radar "
        "did not sign. Rainfall signed, but rainfall alone cannot open a claim. A report says this place "
        "flooded, so under this rule it is a miss. Radar sees open water only: flooding under crops, trees "
        "or buildings is invisible to it.",
    )


# ----------------------------------------------------------------------------
# chain config, checked against the deployment record


def build_config(deployment: dict | None, places: list[dict]) -> dict:
    week_id = event_week(WEEK)
    zones = {}
    for p in places:
        z = zone_id(p["slug"])
        zones[p["slug"]] = {
            "name": p["name"],
            "page": p["page"],
            "zoneId": hexed(z),
            "claimId": hexed(trigger_id(z, week_id, RULE_ID, THRESHOLDS)),
        }
    rain_text = f"{CHIRPS}:2024-05-04:2024-05-06"
    radar_text = f"sentinel-1-rtc:{PUBLISHED_ITEM}"
    config: dict = {
        "chainId": 11155111,
        "chainName": "Sepolia",
        "rpcs": RPCS,
        "explorer": "https://sepolia.etherscan.io",
        "ruleName": RULE["rule_id"],
        "ruleId": hexed(RULE_ID),
        "thresholdsHash": hexed(THRESHOLDS),
        "week": {"text": WEEK, "id": hexed(week_id)},
        "constants": {"challengeWindow": CHALLENGE_WINDOW, "resolveWindow": RESOLVE_WINDOW, "stakeEth": "0.01", "bondEth": "0.01"},
        "zones": zones,
        "evidence": {"radarText": radar_text, "rainText": rain_text},
        # The exact bytes of config/rule.yaml, so a browser can hash them without fetching a file.
        "ruleYamlB64": base64.b64encode((ROOT / "config" / "rule.yaml").read_bytes()).decode("ascii"),
        "trigger": None,
        "escrow": None,
    }
    if not deployment:
        return config

    config["trigger"] = deployment["trigger"]
    config["escrow"] = deployment["escrow"]
    config["roles"] = deployment["roles"]
    config["policyHash"] = deployment["policy_hash"]
    config["snapshot"] = {"at": deployment["snapshot_at"], "block": deployment["block"]}

    # The build refuses to ship ids that disagree with the chain record.
    if deployment["rule_id"].lower() != hexed(RULE_ID):
        raise SystemExit("rule id in deployment.json does not match config/rule.yaml")
    if deployment["thresholds_hash"].lower() != hexed(THRESHOLDS):
        raise SystemExit(
            "thresholdsHash in deployment.json does not match the bytes of config/rule.yaml.\n"
            "The file was probably saved with different line endings. .gitattributes should prevent that."
        )
    for claim in deployment.get("claims", []):
        mine = zones[claim["zone"]]["claimId"]
        if claim["trigger_id"].lower() != mine:
            raise SystemExit(f"claim id for {claim['zone']} differs: {claim['trigger_id']} vs {mine}")
        expected = {"Radar": hexed(evidence_radar(PUBLISHED_ITEM)), "Rainfall": hexed(evidence_rainfall(date(2024, 5, 4), date(2024, 5, 6)))}
        for signer in claim["signers"]:
            if signer["evidence"].lower() != expected[signer["role"]]:
                raise SystemExit(f"{signer['role']} evidence hash differs from the text it claims to hash")
    return config


# ----------------------------------------------------------------------------
# shared pieces

NAV = [
    ("index.html", "Overview", "overview"),
    ("claims.html", "Claims", "claims"),
    ("backtest.html", "Backtest", "backtest"),
    ("payouts.html", "Payouts", "payouts"),
]


def shell(*, title: str, desc: str, key: str, page: str, body: str, zone: str = "") -> str:
    current = ' aria-current="page"'
    nav = "".join(f'<a href="{href}"{current if key == k else ""}>{label}</a>' for href, label, k in NAV)
    zone_attr = f' data-zone="{escape(zone)}"' if zone else ""
    built = datetime.now(timezone.utc).strftime("%d %b %Y")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(desc)}">
<link rel="stylesheet" href="styles.css">
</head>
<body data-page="{page}"{zone_attr}>
<a class="skip" href="#main">Skip to the content</a>
<div class="band" role="note"><div class="wrap"><span><b>Testnet only.</b> Nothing here moves real money.</span><span><b>M-PESA is a sandbox.</b></span><span>Unaudited contracts.</span></div></div>

<header class="mast"><div class="wrap">
  <a class="mark" href="index.html">Aether<span>is</span></a>
  <nav class="nav" aria-label="Pages">{nav}<a href="{REPO}">Code</a></nav>
  <button class="wallet" type="button" data-wallet hidden>Connect wallet</button>
</div></header>

<main id="main">
{body}
</main>

<footer><div class="wrap">
  <div><h3>Check it yourself</h3><ul>
    <li><a href="backtest.html#check">Hash the frozen rule against the contract</a></li>
    <li><a href="{REPO}/blob/main/docs/agreement.md">Agreement table, with pixel counts</a></li>
    <li><a href="{REPO}/blob/main/config/rule.yaml">The frozen rule</a></li>
    <li><a href="{REPO}/blob/main/labels/label_log.csv">Label log and sources</a></li>
  </ul></div>
  <div><h3>Data</h3><ul>
    <li>Sentinel-1 RTC via Microsoft Planetary Computer</li>
    <li>CHIRPS 2.0 daily rainfall</li>
    <li>JRC Global Surface Water</li>
    <li>Place boundaries © OpenStreetMap contributors</li>
  </ul></div>
  <div><h3>These pages</h3><p>Generated {built} from the repository’s own files by <code>web/build.py</code>. Live state is read from Sepolia in your browser. IEEE ClimateChain Global Hackathon 2026, Climate Data &amp; Environmental Monitoring.</p></div>
</div></footer>

<script src="vendor/ethers-6.17.0.umd.min.js" defer></script>
<script src="chain-config.js" defer></script>
<script src="app.js" defer></script>
</body>
</html>
"""


def gauge_radar(p: dict) -> str:
    scale_max = 0.10  # bar scale: 10 % of land pixels; the line sits at 5 %.
    if p["fraction"] is None:
        return '<div class="hatch" role="img" aria-label="No radar measurement">no outline, not measured</div>'
    width = min(p["fraction"] / scale_max, 1.0) * 100
    line_at = RADAR_LINE / scale_max * 100
    return (
        f'<div class="gauge" role="img" aria-label="Open water on {pct(p["fraction"])} of land pixels; '
        f'line at {pct(RADAR_LINE)}"><i class="radar" style="width:{width:.1f}%"></i>'
        f'<b style="left:{line_at:.1f}%"></b></div>'
        f'<span class="pct">{pct(p["fraction"])} of land pixels</span>'
    )


def sign_word(decision: str) -> str:
    if decision == "yes":
        return '<span class="sig"><span class="dot signed"></span>Signed</span>'
    if decision == "abstain":
        return '<span class="sig"><span class="dot na"></span>Not assessed</span>'
    return '<span class="sig"><span class="dot no"></span>Did not sign</span>'


def snapshot_text(slug: str, deployment: dict | None) -> str:
    """What the deploy record said about this place. Shown until the live read replaces it."""
    if not deployment:
        return "Not deployed yet"
    for claim in deployment.get("claims", []):
        if claim["zone"] == slug:
            return "At deploy: both required sources signed, challenge window opened"
    return "At deploy: no claim opened"


def live_bar() -> str:
    return (
        '<div class="livebar"><p class="live-status wait" data-live-status>Reading the Sepolia contracts… '
        "Without scripting this page shows the snapshot taken at deploy time.</p>"
        '<button class="btn small" type="button" data-refresh>Refresh</button></div>'
    )


# ----------------------------------------------------------------------------
# overview


def page_overview(places, counts, deployment) -> str:
    n = len(places)
    rain_signed = sum(1 for p in places if p["rain"] == "yes")
    radar_signed = sum(1 for p in places if p["decision"] == "yes")
    radar_no = sum(1 for p in places if p["decision"] == "no")
    unassessed = sum(1 for p in places if p["decision"] == "abstain")
    rain_line = RULE["rainfall"]["threshold_mm"]
    first_open = next((p for p in places if p["decision"] == "yes" and p["rain"] == "yes"), places[0])

    body = f"""<section class="hero" id="top"><div class="wrap">
  <p class="eyebrow">Verification layer · flood data · Kenya</p>
  <h1>Rain data said “flood” in {WORDS.get(n, n)} places. <em>Radar could confirm {WORDS.get(radar_signed, radar_signed)}.</em></h1>
  <p class="lede">Flood payouts and alerts rest on satellite rainfall estimates that are sparse on the ground and often wrong in heavy rain.
  <strong>Aetheris checks them against Sentinel-1 radar</strong>, which sees whether land is actually under water, for each place and week,
  and records the result where anyone can check it or challenge it. This is the first week we checked: the Nyando basin, {WEEK_TEXT}.</p>
  <p class="cta"><a class="btn primary" href="claims.html">See the claims</a> <a class="btn" href="{first_open['page']}">Open the one live claim</a> <a class="btn" href="backtest.html">Read the backtest</a></p>
  <div class="facts">
    <div class="fact"><span class="n">{n}</span><span class="k">places that news reports said flooded</span></div>
    <div class="fact"><span class="n rain">{rain_signed}</span><span class="k">where rainfall data signed “flood”</span></div>
    <div class="fact"><span class="n radar">{radar_signed}</span><span class="k">where radar also signed, so a claim opened. {radar_no} radar said no; {unassessed} could not be assessed.</span></div>
  </div>
</div></section>

<section class="block" id="why"><div class="wrap">
  <div class="sec-head"><span class="num">01</span><h2>When the data misses the flood, nobody can see why</h2>
  <p>Smallholder farmers and pastoralists in flood-prone basins are paid by weather-index insurance, or helped by alerts, only when the data says a flood happened.
  When that data misses their flood they get nothing, and the decision was made by a single operator, from an estimate, with no reason attached.</p></div>
  <p class="note">Aetheris attaches the reason. Each decision shows what each source measured, against which line, and who signed. It also counts how often the
  data misses real floods, so triggers can be designed more fairly over time. Today the benefit to farmers is indirect, and every payout in this demo is on a testnet or a sandbox.</p>
  <h3 class="h-small gap-l">What the research says</h3>
  <ul class="sources">
    <li><b>Ground stations are few.</b> Africa’s average density of stations meeting WMO standards is eight times below the recommended level, and as of October 2024 Chad was reporting 3% of the surface observations it is required to. <a href="https://eos.org/features/building-better-weather-networks">Eos</a></li>
    <li><b>Satellite rainfall is imperfect where it matters.</b> Against 596 TAHMO gauges, every product tested overestimated light rain and underestimated heavy rain (<a href="https://doi.org/10.1002/essoar.10509210.1">preprint</a>). In East Africa, CHIRPS had a 28% wet bias in daily rainfall (<a href="https://doi.org/10.1175/jhm-d-21-0161.1">published version</a>). Another study found CHIRPS missed 98% of the daily extreme-rain events its gauges recorded (<a href="https://doi.org/10.1175/jhm-d-21-0145.1">36 stations</a>). The studies differ on how good CHIRPS is, so read the numbers with care.</li>
    <li><b>Ground data is gated.</b> ICPAC receives station data from national met services under bilateral agreements, and each service sets its own terms, some with cost recovery. <a href="https://www.icpac.net/events/regional-data-managers-biannual-meeting-on-climate-data-sharing-framework/">ICPAC</a></li>
    <li><b>Index insurance already runs in Kenya on satellite triggers.</b> In 2021 Etherisc and ACRE Africa onboarded more than 17,000 smallholders and began paying some through M-Pesa. <a href="https://blog.etherisc.com/etherisc-update-etherisc-and-acre-africa-announce-first-payouts-through-blockchain-based-platform-a0c5194214f4">Etherisc</a> Those sources do not measure how often such triggers miss a real flood. That is what this project counts.</li>
  </ul>
  <div class="rule-line"><p><b>What is new here, and what is not.</b> We found no published open-code method that cross-validates gauge readings against satellite products. We did not search specifically for radar-versus-rainfall cross-checks, which may exist in the flood-mapping literature, so we do not claim the cross-check itself is new. What we add is recording each disagreement as a signed, challengeable public claim tied to a payout rule.</p></div>
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
  <div class="rule-line"><p><b>The rule is frozen.</b> Radar line: open water below {RULE['radar']['threshold_db']:g} dB on at least {pct(RADAR_LINE)} of land pixels. Rainfall line: {rain_line} mm over three days on the upstream catchment, lag {RULE['rainfall']['lag_days']} days. Fixed on {escape(str(RULE['frozen_on']))}, before this week was scored, and hashed into every claim id. These are untuned starting values, not fitted to this flood. <a href="backtest.html#check">Check the hash against the contract.</a></p></div>
</div></section>

<section class="block" id="users"><div class="wrap">
  <div class="sec-head"><span class="num">03</span><h2>Who this is for, and how we know</h2>
  <p>The direct user is the <b>trigger analyst at an insurer or aggregator</b>: the person who decides what counts as a flood, owns the basis-risk problem, and can use a disagreement record. The people most affected, smallholders and pastoralists, are the beneficiaries, not the users. Data producers and researchers are the community we hope to help, not customers.</p></div>
  <span class="flag">We have not interviewed anyone. The last column says which rows rest on research and which are our assumption.</span>
  <table class="stakeholders">
    <caption>Stakeholders, what each gains, and the basis for saying so</caption>
    <thead><tr><th scope="col">Who</th><th scope="col">Problem they face</th><th scope="col">What Aetheris gives them</th><th scope="col">Basis</th></tr></thead>
    <tbody>
      <tr class="primary"><th scope="row">Insurers and aggregators <span class="tag">Direct user</span></th>
        <td>Triggers can miss real floods or fire without loss (basis risk), and each dispute is costly to settle.</td>
        <td>A per-zone record of where rainfall data and radar agree or disagree, to inform trigger design. <a href="claims.html">Claims →</a></td>
        <td><b>Researched in part.</b> Satellite-triggered index insurance runs in Kenya at scale. That triggers miss floods is our reading of the field; no source above measures it.</td></tr>
      <tr><th scope="row">Disaster responders <span class="note-s">County teams, Red Cross, agencies</span></th>
        <td>Releasing funds or alerts on one forecast or one report is risky and hard to defend.</td>
        <td>A second signal, from a different instrument, before funds or alerts move. <a href="claims.html">Claims →</a></td>
        <td><b>Assumption.</b> Not researched.</td></tr>
      <tr><th scope="row">Data producers <span class="note-s">ICPAC, Kenya Met</span></th>
        <td>Gauges are sparse, station data is gated, and users cannot tell which satellite product to trust.</td>
        <td>An open, repeatable reliability check they can compare against. <a href="backtest.html">Backtest →</a></td>
        <td><b>Researched.</b> Station sparsity, data-sharing terms and rainfall bias are cited above.</td></tr>
      <tr><th scope="row">Researchers and modellers</th>
        <td>Validation studies contradict each other, and gauge data is hard to get.</td>
        <td>An open, repeatable cross-check method. <a href="backtest.html">Backtest →</a></td>
        <td><b>Researched.</b> The CHIRPS studies cited above disagree.</td></tr>
      <tr><th scope="row">Smallholders and pastoralists <span class="note-s">Most affected. Many use feature phones.</span></th>
        <td>Unpaid when the index misses their flood, with no visible reason.</td>
        <td>Indirect: fairer triggers over time, and a visible reason for each decision that an insurer or responder can show them. <a href="{first_open['page']}">See one →</a></td>
        <td><b>Assumption</b>, inferred from the basis-risk research.</td></tr>
    </tbody>
  </table>
  <p class="note"><b>Next step to turn assumptions into evidence:</b> ask one insurer or aggregator whether a disagreement record like this would change how they set triggers. Until that answer exists, treat the rows marked “Assumption” as ours.</p>
</div></section>

<section class="block alt" id="built"><div class="wrap">
  <div class="sec-head"><span class="num">04</span><h2>How it is built, and how much of it exists</h2>
  <p>Data goes in on the left and a payout rule sits on the right. Each part says what state it is really in.</p></div>
  <ol class="pipeline">
    <li><h3>Sources</h3><p>Sentinel-1 radar (RTC), CHIRPS rainfall, JRC permanent water.</p><span class="state part">Read by hand for one week</span></li>
    <li><h3>Frozen rule</h3><p><code>config/rule.yaml</code>. Its hash is part of every claim id.</p><span class="state done">Frozen, hash on the testnet</span></li>
    <li><h3>Attester jobs</h3><p>Radar and rainfall jobs decide sign or stay silent from the rule. Each signs with its own key and bond.</p><span class="state part">Decisions written. The demo claim was submitted by the deploy script with the same keys</span></li>
    <li><h3>FloodTrigger</h3><p>Holds claims, bonds, the challenge window and the referee’s only two choices.</p><span class="state done">Deployed on Sepolia. Unaudited</span></li>
    <li><h3>PayoutEscrow</h3><p>Pays a finalized claim once to a table committed in advance.</p><span class="state done">Deployed on Sepolia. Beneficiaries are placeholders</span></li>
    <li><h3>M-PESA mirror</h3><p>Copies a release into a record labelled SANDBOX.</p><span class="state part">A function that writes a record. No Daraja call is made</span></li>
  </ol>
  <p class="note">Not built: a committee or vote for the referee (one named key decides today), a ground-gauge attester, IMERG rainfall, and any check that real people want this.</p>
</div></section>

<section class="block" id="limits"><div class="wrap">
  <div class="sec-head"><span class="num">05</span><h2>What we are not claiming</h2>
  <p>This is not ground-truth validation, and it does not fix flood insurance.</p></div>
  <ul class="limits">
    <li><b>Radar has blind spots.</b><span>It sees open water. It does not see flood under crops, trees or buildings, and Sentinel-1’s 2024 revisit is twelve days, so a flood can rise and fall between passes.</span></li>
    <li><b>The sources overlap.</b><span>Rainfall and radar describe the same storm. Two signatures are not two independent witnesses, and the agreement table is how we show how much they add.</span></li>
    <li><b>Satellite rainfall is an estimate.</b><span>CHIRPS tends to overestimate light rain and underestimate heavy rain. Gauges are scarce here. IMERG is not connected.</span></li>
    <li><b>The referee is one key.</b><span>In this demo a single named key can uphold or reject a challenge. A committee, then a vote, is the intended path. The contract has one function for it, so swapping does not change the rest.</span></li>
    <li><b>One season, seven news reports.</b><span>Counts here are indicative. Reports favour places that reporters and rescuers could reach. There are no “did not flood” labels yet.</span></li>
    <li><b>Payouts are not real.</b><span>The escrow holds testnet ETH. M-PESA is a Daraja sandbox mirror that moves no money. The contracts are unaudited.</span></li>
  </ul>
</div></section>"""
    return shell(
        title="Aetheris: a verification layer for flood data in Kenya",
        desc="Aetheris cross-checks satellite rainfall against Sentinel-1 radar, place by place and week by week, and records the result on a testnet where anyone can check or challenge it.",
        key="overview",
        page="overview",
        body=body,
    )


# ----------------------------------------------------------------------------
# claims list


def page_claims(places, deployment) -> str:
    n = len(places)
    rain_mm = published_total()
    rain_line = RULE["rainfall"]["threshold_mm"]
    rain_scale = 80.0
    unassessed = sum(1 for p in places if p["decision"] == "abstain")
    rows = []
    for p in places:
        marker, outcome, _ = verdict(p)
        rows.append(
            f"""<li><a class="claimrow" href="{p['page']}">
    <div class="c-name"><span class="name">{escape(p['name'])}</span><span class="scale">{escape(p['scale'])}</span></div>
    <div><span class="cell-label">Radar</span>{gauge_radar(p)}</div>
    <div><span class="cell-label">Rainfall</span>{sign_word(p['rain'])}</div>
    <div><span class="cell-label">What the rule says</span><span class="out"><span class="dot {marker}"></span>{escape(outcome)}</span>
      <span class="cell-label gap">On the testnet</span><span class="live" data-live-zone="{p['slug']}"><span class="snap">{escape(snapshot_text(p['slug'], deployment))}</span></span></div>
    <span class="go" aria-hidden="true">→</span>
  </a></li>"""
        )
    body = f"""<section class="page-head"><div class="wrap">
  <p class="eyebrow">Claims · Nyando basin · {WEEK_TEXT}</p>
  <h1>Seven places, one flood week</h1>
  <p class="lede">News reports named these seven places as flooded. For each one, the rule asks radar and rainfall whether they sign. Where both do, a claim opens on the testnet and anyone can challenge it. Pick a place to see the evidence and the actions open to you.</p>
  {live_bar()}
  <p class="tally" data-live-tally></p>
</div></section>

<section class="block tight"><div class="wrap">
  <div class="catch">
    <div><b>Rainfall, for every place at once.</b> It is read on the upstream headwaters, not on each place, so it gives one answer for the whole week.</div>
    <div class="row">
      <div><div class="gauge" role="img" aria-label="{rain_mm:.1f} millimetres against a line at {rain_line} millimetres"><i class="rain" style="width:{rain_mm / rain_scale * 100:.1f}%"></i><b style="left:{rain_line / rain_scale * 100:.1f}%"></b></div>
      <div class="gauge-scale"><span>0 mm</span><span>line {rain_line} mm</span><span>{rain_scale:g} mm</span></div></div>
      <div><b>{rain_mm:.1f} mm</b> in the three days to 6 May (CHIRPS satellite estimate). Signed for all {n} places.</div>
    </div>
  </div>
  <ul class="legend" aria-label="Key">
    <li><span class="dot signed"></span>Signed</li><li><span class="dot half"></span>In progress</li><li><span class="dot no"></span>Did not sign, or no claim</li><li><span class="dot na"></span>Could not assess</li>
    <li><span class="sw radar"></span>Radar: share of land that looks like open water</li><li><span class="sw line"></span>The rule’s line</li>
  </ul>
  <div class="board-head claims" aria-hidden="true"><div>Place</div><div>Radar</div><div>Rainfall</div><div>Outcome</div><div></div></div>
  <ul class="board claims">
{chr(10).join(rows)}
  </ul>
  <p class="note">Boxes are working extents from OpenStreetMap, not surveyed flood outlines. {unassessed} places were left unassessed rather than measured at the wrong location.
  “What the rule says” is computed from the data. “On the testnet” is read from the contract. The six places without a claim are not hidden failures: the rule did not fire there, and the chain agrees.</p>
</div></section>"""
    return shell(
        title="Claims · Aetheris",
        desc="The seven places reported flooded in the Nyando basin, 4–6 May 2024, with what radar and rainfall each said and the live state of each claim on Sepolia.",
        key="claims",
        page="claims",
        body=body,
    )


# ----------------------------------------------------------------------------
# one claim


def page_claim(p: dict, deployment) -> str:
    marker, outcome, why = verdict(p)
    slug = p["slug"]
    rain_mm = published_total()
    rain_line = RULE["rainfall"]["threshold_mm"]
    rain_scale = 80.0
    expect_radar = hexed(evidence_radar(PUBLISHED_ITEM))
    expect_rain = hexed(evidence_rainfall(date(2024, 5, 4), date(2024, 5, 6)))
    opens = p["decision"] == "yes" and p["rain"] == "yes"

    radar_rows = [
        ("Radar scene", f'<a href="https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-1-rtc/items/{escape(PUBLISHED_ITEM)}">{escape(PUBLISHED_ITEM)}</a>'),
        ("Water test", escape(f"VV below {RULE['radar']['threshold_db']:g} dB, land pixels only")),
    ]
    if p["land"] is not None:
        radar_rows += [
            ("Land pixels read", f"{p['land']:,}"),
            ("Looked like water", f"{p['flooded']:,}"),
            ("Permanent water removed", escape(f"{p['removed']:,} pixels (JRC occurrence ≥ {RULE['radar']['permanent_water_occurrence']})")),
        ]
    radar_rows.append(("Area measured", escape(p["box_note"])))
    radar_dl = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in radar_rows)

    if deployment and opens:
        chain_block = f"""<section class="block"><div class="wrap">
  <div class="sec-head"><span class="num">03</span><h2>What is on the testnet</h2>
  <p>The state below is read from the contract when you open this page. The evidence hashes are recomputed in your browser from the public text, so you can see that each signature names exactly the evidence described above.</p></div>
  {live_bar()}
  <div class="panel stakebox"><h3>What is at stake</h3><div data-live-stake><p class="note">Reading…</p></div></div>
  <div class="two">
    <div><h3 class="h-small">Signatures</h3><div data-live-signatures><p class="note">Reading…</p></div>
      <p class="note">Expected radar hash: <code>{expect_radar}</code><br>Expected rainfall hash: <code>{expect_rain}</code></p></div>
    <div><h3 class="h-small">Timeline</h3><ul class="tl" data-live-timeline><li>Reading the event history…</li></ul></div>
  </div>
</div></section>"""
    elif deployment:
        chain_block = f"""<section class="block"><div class="wrap">
  <div class="sec-head"><span class="num">03</span><h2>What is on the testnet</h2>
  <p>No signature exists for this place. The rule did not fire here, so neither attester signed, and the contract holds nothing for it. Silence counts as no.</p></div>
  {live_bar()}
  <div class="panel stakebox"><h3>What is at stake</h3><div data-live-stake><p class="note">Reading…</p></div></div>
  <div data-live-signatures></div><ul class="tl" data-live-timeline hidden></ul>
</div></section>"""
    else:
        chain_block = """<section class="block"><div class="wrap"><div class="sec-head"><h2>Not deployed yet</h2></div></div></section>"""

    claim_id = zone_claim_id(slug)
    actions = ""
    if deployment:
        actions = f"""<section class="block alt" id="actions"><div class="wrap">
  <div class="sec-head"><span class="num">04</span><h2>What can be done with this claim</h2>
  <p>Five things can happen to a claim, and each belongs to someone. The buttons enable themselves only when the contract would accept them, judged by the chain’s clock. A refusal is explained in words.</p></div>
  <div class="try"><b>To try it</b> you need a browser wallet on Sepolia with a little test ETH: 0.01 to challenge, plus gas. Reading needs no wallet.
    If you challenge, the referee key is one key held by the project team, and it has 48 hours to decide. If it stays silent the claim stands and your stake comes back.</div>
  <label class="confirm"><input type="checkbox" data-confirm-challenge> I understand a challenge stakes 0.01 Sepolia test ETH.</label>
  <div class="acts" data-live-actions><p class="note">Reading the claim…</p></div>
  <p class="txlog" data-tx-log hidden></p>
</div></section>"""

    body = f"""<section class="page-head"><div class="wrap">
  <p class="crumb"><a href="claims.html">Claims</a> / {escape(p['name'])}</p>
  <h1>{escape(p['name'])}, {WEEK_TEXT}</h1>
  <p class="scale-line">{escape(p['scale'])}</p>
  <div class="stage snapshot" data-live-stage>
    <div class="stage-head"><span class="chip"><span class="dot {marker}"></span>{escape(outcome)}</span></div>
    <p class="stage-detail">{escape(snapshot_text(slug, deployment))}. Live state loads below when scripting is on.</p>
  </div>
</div></section>

<section class="block"><div class="wrap">
  <div class="sec-head"><span class="num">01</span><h2>The reason for this decision</h2></div>
  <div class="reason"><p>{escape(why)}</p></div>
  <div class="two">
    <div class="panel"><span class="who radar">Radar</span> {sign_word(p['decision'])}
      <div class="gap-s">{gauge_radar(p)}</div>
      <dl>{radar_dl}</dl></div>
    <div class="panel"><span class="who rain">Rainfall</span> {sign_word(p['rain'])}
      <div class="gap-s"><div class="gauge" role="img" aria-label="{rain_mm:.1f} millimetres against a line at {rain_line} millimetres"><i class="rain" style="width:{rain_mm / rain_scale * 100:.1f}%"></i><b style="left:{rain_line / rain_scale * 100:.1f}%"></b></div>
      <div class="gauge-scale"><span>0 mm</span><span>line {rain_line} mm</span><span>{rain_scale:g} mm</span></div></div>
      <dl><dt>Total</dt><dd>{rain_mm:.1f} mm over the three days to 6 May</dd>
      <dt>Source</dt><dd>CHIRPS 2.0 daily, a satellite estimate</dd>
      <dt>Where</dt><dd>Upstream catchment <code>{escape(RULE['rainfall']['catchment_id'])}</code>, not this place</dd>
      <dt>Line</dt><dd>{rain_line} mm over {RULE['rainfall']['window_days']} days, lag {RULE['rainfall']['lag_days']} days</dd></dl></div>
  </div>
</div></section>

<section class="block alt"><div class="wrap">
  <div class="sec-head"><span class="num">02</span><h2>Why this place was counted as flooded</h2></div>
  <p class="note-wide">{escape(p['label_note'])}</p>
  <p class="note-wide"><a href="{escape(p['label_url'])}">{escape(p['label_source'])}</a>, reported 4–5 May 2024. A news report is a label, not a survey.</p>
</div></section>

{chain_block}
{actions}

<section class="block"><div class="wrap">
  <div class="sec-head"><span class="num">{'05' if deployment else '04'}</span><h2>The identifiers, so you can recompute them</h2>
  <p>The claim id is <code>keccak256(zoneId, eventWeek, ruleId, thresholdsHash)</code>. Change the rule and the id changes, so a claim cannot be moved onto a different rule.</p></div>
  <dl class="ids">
    <dt>Claim id</dt><dd><code>{claim_id}</code></dd>
    <dt>Zone id</dt><dd><code>{hexed(zone_id(slug))}</code> = keccak256(“{slug}”)</dd>
    <dt>Event week</dt><dd><code>{hexed(event_week(WEEK))}</code> = keccak256(“{WEEK}”)</dd>
    <dt>Rule id</dt><dd><code>{hexed(RULE_ID)}</code> = keccak256(“{escape(RULE['rule_id'])}”)</dd>
    <dt>Thresholds hash</dt><dd><code>{hexed(THRESHOLDS)}</code> = keccak256(config/rule.yaml)</dd>
  </dl>
</div></section>"""
    return shell(
        title=f"{p['name']} · Aetheris",
        desc=f"What radar and rainfall each said about {p['name']} for {WEEK_TEXT}, why the place was counted as flooded, and the live state of its claim on Sepolia.",
        key="claims",
        page="claim",
        body=body,
        zone=slug,
    )


def zone_claim_id(slug: str) -> str:
    return hexed(trigger_id(zone_id(slug), event_week(WEEK), RULE_ID, THRESHOLDS))


# ----------------------------------------------------------------------------
# backtest


def render_matrix(places) -> str:
    cells = {
        ("yes", "yes"): [p for p in places if p["decision"] == "yes" and p["rain"] == "yes"],
        ("no", "yes"): [p for p in places if p["decision"] == "no" and p["rain"] == "yes"],
        ("abstain", "yes"): [p for p in places if p["decision"] == "abstain" and p["rain"] == "yes"],
    }

    def cell(key, highlight=False):
        group = cells[key]
        if not group:
            return '<td class="zero n">0</td>'
        cls = ' class="hl"' if highlight else ""
        return f'<td{cls}><span class="big">{len(group)}</span><small>{escape(", ".join(p["name"] for p in group))}</small></td>'

    zero = '<td class="zero n">0</td>'
    return f"""<table class="matrix">
  <caption>Radar (rows) against rainfall (columns), {len(places)} places reported flooded</caption>
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


def render_misses(counts: dict) -> str:
    names = {
        "no_scene": "Radar had no pass that week",
        "below_threshold": "Radar saw too little open water",
        "uncorroborated": "Radar signed, the second source did not",
        "rainfall_gap": "Rainfall data was missing",
        "no_geometry": "No outline to measure, radar not run",
    }
    rows = "".join(
        f'<tr><th scope="row">{escape(label)}</th><td class="n">{counts["misses"].get(key, 0)}</td></tr>' for key, label in names.items()
    )
    return f"""<table>
  <caption>Why the reported floods that produced no claim were missed</caption>
  <thead><tr><th></th><th class="n">Places</th></tr></thead>
  <tbody>{rows}</tbody>
</table>"""


def page_backtest(places, counts) -> str:
    n = len(places)
    radar_signed = sum(1 for p in places if p["decision"] == "yes")
    radar_no = sum(1 for p in places if p["decision"] == "no")
    unassessed = sum(1 for p in places if p["decision"] == "abstain")
    rule_miss = counts["rules"]["radar_plus_rainfall"]["misses"]
    files = [
        ("counts.csv", "Every count on this page", "backtest/results/counts.csv"),
        ("label_log.csv", "The seven places and the reports that named them", "labels/label_log.csv"),
        ("radar_fractions.csv", "Radar fraction and pixel counts per place", "backtest/checks/radar_fractions.csv"),
        ("observations.csv", "What each source signed, per place", "backtest/observations.csv"),
        ("rule.yaml", "The frozen rule, byte for byte (its hash is on the testnet)", "config/rule.yaml"),
    ]
    downloads = "".join(
        f'<li><a href="data/{name}" download>{name}</a><span>{escape(desc)} · <code>{src}</code></span></li>' for name, desc, src in files
    )
    body = f"""<section class="page-head"><div class="wrap">
  <p class="eyebrow">Backtest · one season · counts only</p>
  <h1>Where the sources agreed, disagreed, and what was missed</h1>
  <p class="lede">One flood week, {n} places, one frozen rule. We report counts, not an accuracy percentage, because seven news reports cannot carry one. The rule was fixed on {escape(str(RULE['frozen_on']))}, before this week was scored, and we did not tune it afterwards.</p>
</div></section>

<section class="block"><div class="wrap">
  <div class="sec-head"><span class="num">01</span><h2>Agreement</h2>
  <p>The rows where the sources disagree are the only rows where the second source changes the result.</p></div>
  <div class="matrix-wrap">
    <div>{render_matrix(places)}</div>
    <div>{render_rules(counts)}</div>
  </div>
  <div class="takeaway">
    <p><b>Rainfall was “yes” in every place, so it told us almost nothing about which places flooded.</b> It disagreed with radar in {radar_no} of the {radar_signed + radar_no} places radar could judge.</p>
    <p>Requiring radar means {rule_miss} of {n} reported floods produced no claim: {radar_no} where radar saw too little open water, and {unassessed} where it could not look. Rainfall alone would have found all {n}, but there is no “did not flood” place in this log, so we cannot say how often rainfall alone would raise a false alarm. Neither number is an accuracy figure. They are counts from one week.</p>
    <p>Misses caused by radar having no pass that week: <b>{counts['misses']['no_scene']}</b>. The 6 May scene existed.</p>
  </div>
  <div class="matrix-wrap gap-l"><div>{render_misses(counts)}</div><div></div></div>
</div></section>

<section class="block alt" id="check"><div class="wrap">
  <div class="sec-head"><span class="num">02</span><h2>Check that the rule on the chain is the rule in the repository</h2>
  <p>Each claim id contains a hash of <code>config/rule.yaml</code>. This button hashes the file here, in your browser, then asks the contract what hash it holds. If someone had changed the rule after the fact, they would not match.</p></div>
  <button class="btn primary" type="button" data-check-rule disabled>Hash the rule and compare</button>
  <div data-check-out class="check-out" aria-live="polite"></div>
  <p class="note">The file is stored byte for byte, line endings included, because the hash covers every byte. See <a href="{REPO}/blob/main/.gitattributes"><code>.gitattributes</code></a>.</p>
</div></section>

<section class="block"><div class="wrap">
  <div class="sec-head"><span class="num">03</span><h2>Download the data</h2>
  <p>These are copies of the repository files the numbers are computed from.</p></div>
  <ul class="downloads">{downloads}</ul>
</div></section>

<section class="block alt"><div class="wrap">
  <div class="sec-head"><span class="num">04</span><h2>Reproduce it</h2>
  <p>From a clone of <a href="{REPO}">the repository</a>, with Python 3:</p></div>
<pre class="cmd"><code>python -m backtest.score          # reads labels/label_log.csv and backtest/observations.csv
                                  # writes backtest/results/counts.csv
python -m unittest backtest.test_score backtest.pipeline.test_pipeline watcher.test_mirror
python web/build.py               # rebuilds these pages from the same files</code></pre>
  <p class="note">The radar fractions come from <code>backtest/checks/radar_fraction.py</code>, which needs network access to Microsoft Planetary Computer. The scored result does not depend on rerunning it: the measured values are in the CSV above.</p>
</div></section>

<section class="block"><div class="wrap">
  <div class="sec-head"><span class="num">05</span><h2>What this cannot tell you</h2></div>
  <ul class="limits">
    <li><b>No “did not flood” labels.</b><span>Without them there are no false alarms to count, so no precision, and we publish none.</span></li>
    <li><b>Seven reports favour reachable places.</b><span>Places that reporters and rescuers could reach are over-represented. Unknown is not “no flood”.</span></li>
    <li><b>Boxes are not flood outlines.</b><span>A ward box mixes dry and wet land, which pulls the radar fraction down. That is one reason radar says no in {radar_no} places.</span></li>
    <li><b>One week.</b><span>Nothing here says how the rule behaves in another season. It is a frozen first rule, to be judged on a season it has not seen.</span></li>
  </ul>
</div></section>"""
    return shell(
        title="Backtest · Aetheris",
        desc="Agreement, disagreement and misses between satellite rainfall and Sentinel-1 radar for the Nyando basin flood week, as counts, with downloads and a way to reproduce them.",
        key="backtest",
        page="backtest",
        body=body,
    )


# ----------------------------------------------------------------------------
# payouts


def page_payouts(deployment) -> str:
    if not deployment:
        main = '<section class="block"><div class="wrap"><div class="sec-head"><h2>Not deployed yet</h2></div></div></section>'
    else:
        main = f"""<section class="block"><div class="wrap">
  <div class="sec-head"><span class="num">01</span><h2>The escrow</h2>
  <p>A contract holds testnet ETH and pays only a finalized claim, once, to a table fixed before any claim existed. The funder cannot take money back during the season, and can reclaim only what was never credited after it ends.</p></div>
  {live_bar()}
  <div class="two">
    <div class="panel"><h3>Pool</h3><div data-live-escrow><p class="note">Reading…</p></div></div>
    <div class="panel"><h3>Contracts</h3><dl>
      <dt>PayoutEscrow</dt><dd><a href="{deployment['explorer']}/address/{deployment['escrow']['address']}"><code>{deployment['escrow']['address']}</code></a></dd>
      <dt>FloodTrigger</dt><dd><a href="{deployment['explorer']}/address/{deployment['trigger']['address']}"><code>{deployment['trigger']['address']}</code></a></dd>
      <dt>Funder</dt><dd><a href="{deployment['explorer']}/address/{deployment['roles']['funder']}"><code>{deployment['roles']['funder']}</code></a></dd></dl></div>
  </div>
</div></section>

<section class="block alt"><div class="wrap">
  <div class="sec-head"><span class="num">02</span><h2>Who gets paid, and when</h2>
  <p>This table is the committed policy, read from the escrow. It was locked before the pool was funded, so it cannot change.</p></div>
  <div class="warn"><b>The beneficiaries in this deployment are placeholders.</b> Each is an address derived from a hash, and nobody holds a key for it. A release would credit them correctly, and the ETH would then sit there. A real deployment commits real recipients, such as an insurer’s payout account or an aggregator’s wallet.</div>
  <table class="grants"><caption>Committed grants, one per place</caption>
    <thead><tr><th scope="col">Place</th><th scope="col">Beneficiary</th><th class="n" scope="col">Amount</th><th scope="col">Claim state</th></tr></thead>
    <tbody data-live-grants><tr><td colspan="4">Reading…</td></tr></tbody></table>
  <h3 class="h-small gap-l">Released so far</h3>
  <ul class="tl" data-live-released><li>Reading…</li></ul>
</div></section>

<section class="block"><div class="wrap">
  <div class="sec-head"><span class="num">03</span><h2>Withdraw</h2>
  <p>Money never gets pushed to anyone. Returned bonds, returned stakes, slashed bonds and payouts all wait as a balance that the owner pulls. Connect a wallet to see yours.</p></div>
  <div class="acts" data-live-withdraw></div>
  <p class="txlog" data-tx-log hidden></p>
</div></section>"""
    body = f"""<section class="page-head"><div class="wrap">
  <p class="eyebrow">Payouts · testnet ETH · M-PESA sandbox</p>
  <h1>Money moves once, and only after a claim finalizes</h1>
  <p class="lede">Nothing on this page moves real money. The escrow holds Sepolia test ETH. The M-PESA step below is a labelled sandbox record and calls no payment service.</p>
</div></section>
{main}
<section class="block alt"><div class="wrap">
  <div class="sec-head"><span class="num">04</span><h2>The M-PESA sandbox mirror</h2>
  <p>When the escrow emits a release, <code>watcher/mirror.py</code> turns it into a record that a Daraja sandbox client could read. Today that is all it does.</p></div>
  <div class="two">
    <div class="panel"><span class="status wait">Sandbox</span><h3>What exists</h3>
      <p>A function that copies one finalized release into a record. Every record is labelled <code>SANDBOX</code> and says no money moved.</p>
      <p>It does not call Safaricom, hold credentials, or send shillings. It is not running as a service, so no record has been written for this deployment.</p></div>
    <div class="panel"><h3>The shape of a record</h3>
<pre class="cmd"><code>{{
  "label": "SANDBOX",
  "rail": "daraja-sandbox",
  "moved_kes": false,
  "trigger_id": "&lt;claim id&gt;",
  "zone": "&lt;place&gt;",
  "amount_wei": &lt;wei released&gt;
}}</code></pre>
      <p class="note">This is the format, not a payout. No example amount is shown, because none has been released.</p></div>
  </div>
</div></section>"""
    return shell(
        title="Payouts · Aetheris",
        desc="The testnet escrow behind Aetheris: the committed payout table, the pool, withdrawals, and the M-PESA sandbox mirror, which moves no money.",
        key="payouts",
        page="payouts",
        body=body,
    )


# ----------------------------------------------------------------------------
# write everything


def copy_data() -> None:
    out = WEB / "data"
    out.mkdir(exist_ok=True)
    for src, name in [
        (ROOT / "backtest" / "results" / "counts.csv", "counts.csv"),
        (ROOT / "labels" / "label_log.csv", "label_log.csv"),
        (ROOT / "backtest" / "checks" / "radar_fractions.csv", "radar_fractions.csv"),
        (ROOT / "backtest" / "observations.csv", "observations.csv"),
        (ROOT / "config" / "rule.yaml", "rule.yaml"),  # byte for byte: its hash is on the chain
    ]:
        shutil.copyfile(src, out / name)


def render_all() -> tuple[dict[str, str], dict]:
    """Every page as text, plus the chain config. Raises if ids disagree with the deployment record."""
    places = load_places()
    counts = load_counts()
    deployment = json.loads(DEPLOYMENT.read_text(encoding="utf-8")) if DEPLOYMENT.exists() else None
    config = build_config(deployment, places)
    pages = {"index.html": page_overview(places, counts, deployment), "claims.html": page_claims(places, deployment),
             "backtest.html": page_backtest(places, counts), "payouts.html": page_payouts(deployment)}
    for p in places:
        pages[p["page"]] = page_claim(p, deployment)
    return pages, config


def main() -> None:
    pages, config = render_all()
    for name, html in pages.items():
        (WEB / name).write_text(html, encoding="utf-8", newline="\n")

    (WEB / "chain-config.js").write_text(
        "/* Written by web/build.py. Addresses and ids only; no keys. */\nwindow.AETHERIS = " + json.dumps(config, indent=1) + ";\n",
        encoding="utf-8",
        newline="\n",
    )
    copy_data()
    print(f"wrote {len(pages)} pages, chain-config.js and data/ in {WEB}")


if __name__ == "__main__":
    main()
