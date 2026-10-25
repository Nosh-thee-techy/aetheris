"""Stakeholder workspaces.

Each page is a tool for one job, built only from numbers the rest of the
site already has. The reinsurer page is layered like a catastrophe model
(hazard, exposure, loss, unmodeled). It is one named event, not a
stochastic catalogue, and the page says so.
"""

from __future__ import annotations

from html import escape

# Demo grant per place, the same value contracts/tools/deploy_testnet.mjs posts.
GRANT_ETH = 0.001


def grant_sum(n: int) -> str:
    return f"{n * GRANT_ETH:.3f}"


def groups(places: list[dict]) -> dict[str, list[dict]]:
    return {
        "modeled": [p for p in places if p["decision"] == "yes" and p["rain"] == "yes"],
        "radar_no": [p for p in places if p["decision"] == "no"],
        "unassessed": [p for p in places if p["decision"] == "abstain"],
        "rainfall": [p for p in places if p["rain"] == "yes"],
    }


WORKSPACES = [
    ("for-insurer.html", "Insurer", "insurer"),
    ("for-reinsurer.html", "Reinsurer", "reinsurer"),
    ("for-responder.html", "Responder", "responder"),
    ("for-data.html", "Data", "data"),
    ("for-research.html", "Research", "research"),
    ("for-farmer.html", "Farmer view", "farmer"),
]


def workspace_nav(current: str) -> str:
    parts = ['<nav class="ws-nav" aria-label="Workspaces"><a href="workspaces.html">All workspaces</a>']
    for href, label, key in WORKSPACES:
        current_attr = ' aria-current="page"' if current == key else ""
        parts.append(f'<a href="{href}"{current_attr}>{escape(label)}</a>')
    parts.append("</nav>")
    return "".join(parts)


def names(places: list[dict]) -> str:
    return escape(", ".join(p["name"] for p in places)) if places else "None"


def render_all(build, places, counts, deployment) -> dict[str, str]:
    """Every workspace page, wrapped in the site shell."""
    return {
        "workspaces.html": _wrap(build, "workspaces", page_hub(build, places)),
        "for-insurer.html": _wrap(build, "insurer", page_insurer(build, places, counts, deployment)),
        "for-reinsurer.html": _wrap(build, "reinsurer", page_reinsurer(build, places, counts, deployment)),
        "for-responder.html": _wrap(build, "responder", page_responder(build, places, deployment)),
        "for-data.html": _wrap(build, "data", page_data(build, places, counts)),
        "for-research.html": _wrap(build, "research", page_research(build, places, counts)),
        "for-farmer.html": _wrap(build, "farmer", page_farmer(build, places)),
    }


def _wrap(build, key: str, body: str) -> str:
    titles = {
        "workspaces": ("Workspaces · Aetheris", "A workspace for each person who uses flood triggers: insurer, reinsurer, responder, data producer, researcher, and a plain view for a farmer."),
        "insurer": ("Insurer workspace · Aetheris", "What each trigger rule would have done in the Nyando basin in the week of 4–6 May 2024, and the one live claim you can challenge."),
        "reinsurer": ("Reinsurer workspace · event loss · Aetheris", "Hazard, exposure, modeled loss and the unmodeled residual for one named Nyando flood. One event, not a catastrophe model."),
        "responder": ("Responder workspace · Aetheris", "Which reported floods in Nyando, 4–6 May 2024, have a second signal from radar, which have rainfall only, and which could not be assessed."),
        "data": ("Data workspace · Aetheris", "How CHIRPS and Sentinel-1 each behaved on the Nyando flood week, with downloads and a way to hash the frozen rule."),
        "research": ("Research workspace · Aetheris", "The open method, the agreement table, and the files needed to reproduce the Nyando flood-week counts."),
        "farmer": ("Farmer view · Aetheris", "What the rule said about each place in the Nyando basin, 4–6 May 2024, in plain language. No money moves from this page."),
    }
    title, desc = titles[key]
    return build.shell(title=title, desc=desc, key="workspaces", page="workspace", body=body)


def page_hub(build, places) -> str:
    g = groups(places)
    cards = [
        ("for-insurer.html", "Insurer or aggregator", "Trigger analyst",
         "See what rainfall-only would have paid, what this rule paid, and challenge the live claim.",
         f"{len(g['rainfall'])} rainfall-only · {len(g['modeled'])} opened"),
        ("for-reinsurer.html", "Reinsurer", "Event loss",
         "A layered footprint of one named flood: hazard, demo exposure, modeled loss, unmodeled residual.",
         f"{grant_sum(len(g['modeled']))} ETH modeled · {grant_sum(len(g['radar_no']) + len(g['unassessed']))} ETH unmodeled"),
        ("for-responder.html", "Disaster responder", "Second signal",
         "Act where radar also signed. Hold where only rainfall signed. Do not invent a reading where we could not look.",
         f"{len(g['modeled'])} with a second signal · {len(g['radar_no'])} rainfall only · {len(g['unassessed'])} cannot assess"),
        ("for-data.html", "ICPAC, Kenya Met", "Source reliability",
         "Which product signed, which abstained, and the files to compare against your own.",
         f"Radar assessed {len(g['modeled']) + len(g['radar_no'])} of {len(places)}"),
        ("for-research.html", "Researcher or modeller", "Open method",
         "Counts, the frozen rule, downloads, and the commands that rebuild them.",
         "Counts only. No accuracy figure."),
        ("for-farmer.html", "Smallholder or pastoralist", "Plain view",
         "What the rule said about a place, in one sentence. An insurer or responder can show this page.",
         "No wallet. No money moves."),
    ]
    items = "".join(
        f"""<a class="ws-card" href="{href}">
    <span class="who-tag">{escape(who)}</span>
    <h3>{escape(title)}</h3>
    <p>{escape(blurb)}</p>
    <p class="ws-meta">{escape(meta)}</p>
  </a>"""
        for href, title, who, blurb, meta in cards
    )
    return f"""<section class="page-head"><div class="wrap">
  <p class="eyebrow">Workspaces · one job each</p>
  <h1>A tool for the person who actually uses it</h1>
  <p class="lede">The claims list is for the trigger analyst. Everyone else was getting a paragraph. Each workspace below is built from the same seven places and the same frozen rule. None of them invents a reading we did not take.</p>
</div></section>
<section class="block tight"><div class="wrap">
  <div class="ws-grid">{items}</div>
  <p class="note">We have not interviewed these users. The reinsurer page is shaped like a catastrophe-model event, because that is how they already read a flood. It is still one week.</p>
</div></section>"""


def page_insurer(build, places, counts, deployment) -> str:
    g = groups(places)
    rain_mm = build.published_total()
    rain_line = build.RULE["rainfall"]["threshold_mm"]
    first = g["modeled"][0] if g["modeled"] else places[0]
    rows = []
    for p in places:
        marker, outcome, _ = build.verdict(p)
        kind = "Would open" if p in g["modeled"] else ("Rainfall only — no claim" if p["decision"] == "no" else "Cannot assess")
        rows.append(
            f"""<tr>
    <th scope="row"><a href="{p['page']}">{escape(p['name'])}</a><span class="note-s">{escape(p['scale'])}</span></th>
    <td>{build.sign_word(p['rain'])}</td>
    <td>{build.sign_word(p['decision'])}</td>
    <td><span class="dot {marker}"></span> {escape(kind)}</td>
    <td class="live" data-live-zone="{p['slug']}"><span class="snap">{escape(build.snapshot_text(p['slug'], deployment))}</span></td>
  </tr>"""
        )
    return f"""<section class="page-head"><div class="wrap">
  {workspace_nav("insurer")}
  <p class="eyebrow">Insurer workspace · trigger design</p>
  <h1>Your rainfall trigger would have paid {len(g['rainfall'])}. This rule paid {len(g['modeled'])}.</h1>
  <p class="lede">That gap is the basis-risk record. Rainfall signed everywhere because it is read once, on the upstream catchment. Radar looks at each place. Use the disagreement to defend a stricter trigger, or to argue the line is too high.</p>
  {build.live_bar()}
</div></section>
<section class="block"><div class="wrap">
  <div class="sec-head"><span class="num">01</span><h2>What each rule would have done</h2>
  <p>Same seven places, same week, three rules. False triggers stay at zero because this log has no “did not flood” labels.</p></div>
  <div class="matrix-wrap">
    <div>{build.render_rules(counts)}</div>
    <div>{build.render_matrix(places)}</div>
  </div>
</div></section>
<section class="block alt"><div class="wrap">
  <div class="sec-head"><span class="num">02</span><h2>Place by place</h2>
  <p>Rainfall: {rain_mm:.1f} mm against a line at {rain_line:g} mm, one answer for every place. Radar line: {build.pct(build.RADAR_LINE)} of land pixels.</p></div>
  <div class="matrix-wrap"><div>
  <table class="grants"><caption>Trigger outcome per place</caption>
    <thead><tr><th scope="col">Place</th><th scope="col">Rainfall</th><th scope="col">Radar</th><th scope="col">This rule</th><th scope="col">On the testnet</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table></div></div>
  <p class="note">{len(g['unassessed'])} places have no outline we would stand behind. That is a geometry problem, not a weather problem, and it should not be priced as “no flood”.</p>
</div></section>
<section class="block"><div class="wrap">
  <div class="sec-head"><span class="num">03</span><h2>The one live claim</h2>
  <p>{escape(first['name'])} is the only place both sources signed. Anyone can challenge it. The referee is one named key.</p></div>
  <p class="cta"><a class="btn primary" href="{first['page']}">Open {escape(first['name'])}</a> <a class="btn" href="claims.html">All claims</a></p>
</div></section>"""


def page_reinsurer(build, places, counts, deployment) -> str:
    g = groups(places)
    n = len(places)
    rain_mm = build.published_total()
    rain_line = build.RULE["rainfall"]["threshold_mm"]
    modeled_n = len(g["modeled"])
    rain_n = len(g["rainfall"])
    unmodeled_n = len(g["radar_no"]) + len(g["unassessed"])
    modeled_w = modeled_n / n * 100
    hazard_rows = []
    for p in places:
        if p["fraction"] is None:
            frac = "—"
            vs = "No outline. Not measured."
        else:
            frac = build.pct(p["fraction"])
            vs = "Above the line" if p["decision"] == "yes" else "Below the line"
        hazard_rows.append(
            f"<tr><th scope='row'>{escape(p['name'])}</th>"
            f"<td class='n'>{frac}</td><td>{escape(vs)}</td>"
            f"<td>{build.sign_word(p['decision'])}</td></tr>"
        )
    unmodeled_rows = []
    for p in g["radar_no"]:
        unmodeled_rows.append(
            f"<tr><th scope='row'>{escape(p['name'])}</th>"
            f"<td>Radar saw {build.pct(p['fraction'])} open water, below {build.pct(build.RADAR_LINE)}.</td>"
            f"<td class='n'>{grant_sum(1)} ETH</td></tr>"
        )
    for p in g["unassessed"]:
        unmodeled_rows.append(
            f"<tr><th scope='row'>{escape(p['name'])}</th>"
            f"<td>No outline we would stand behind. Radar was not run.</td>"
            f"<td class='n'>{grant_sum(1)} ETH</td></tr>"
        )
    live_claim = g["modeled"][0]["page"] if g["modeled"] else "claims.html"
    return f"""<section class="page-head"><div class="wrap">
  {workspace_nav("reinsurer")}
  <p class="eyebrow">Reinsurer workspace · event loss</p>
  <h1>Nyando basin, {build.WEEK_TEXT}. One event. <em>Not a catastrophe model.</em></h1>
  <p class="lede">A cat model needs thousands of simulated years, a vulnerability function, and your own exposure file. What we can give you honestly is the footprint of one named flood, layered the way you already read an event: hazard, exposure, modeled loss, and the residual the rule left unmodeled. Put it in your model. Do not treat this page as the model.</p>
  {build.live_bar()}
  <div class="facts">
    <div class="fact"><span class="n">{modeled_n}</span><span class="k">place the rule modeled as a loss</span></div>
    <div class="fact"><span class="n rain">{unmodeled_n}</span><span class="k">reported floods left unmodeled</span></div>
    <div class="fact"><span class="n radar">{grant_sum(modeled_n)}</span><span class="k">ETH modeled · {grant_sum(rain_n)} ETH if the trigger were rainfall only. Demo amounts, not sums insured.</span></div>
  </div>
</div></section>

<section class="block" id="hazard"><div class="wrap">
  <div class="sec-head"><span class="num">01</span><h2>Hazard</h2>
  <p>Two measurements of the same storm. They are not two independent witnesses.</p></div>
  <div class="layers">
    <div class="layer">
      <h3>Rainfall · CHIRPS 2.0</h3>
      <p class="n-lg">{rain_mm:.1f} mm</p>
      <p>Three-day catchment total against a line at {rain_line:g} mm. One reading, applied to every place. Signed in {rain_n} of {n}.</p>
    </div>
    <div class="layer">
      <h3>Radar · Sentinel-1</h3>
      <p class="n-lg">{modeled_n} signed</p>
      <p>Open water on a place’s land, permanent water removed, line at {build.pct(build.RADAR_LINE)}. {len(g['radar_no'])} below the line. {len(g['unassessed'])} not measured.</p>
    </div>
  </div>
  <div class="matrix-wrap gap-l"><div>
  <table class="grants"><caption>Radar fraction against the {build.pct(build.RADAR_LINE)} line</caption>
    <thead><tr><th scope="col">Place</th><th class="n" scope="col">Open water</th><th scope="col">Against the line</th><th scope="col">Radar</th></tr></thead>
    <tbody>{"".join(hazard_rows)}</tbody>
  </table></div></div>
</div></section>

<section class="block alt" id="exposure"><div class="wrap">
  <div class="sec-head"><span class="num">02</span><h2>Exposure</h2>
  <p>Each place carries a demo grant of {GRANT_ETH} ETH, posted so the escrow can show a payout. The beneficiaries are placeholder addresses. A real treaty would load your own sums insured and your own recipients here.</p></div>
  <dl class="stake">
    <dt>Places in the book</dt><dd>{n}</dd>
    <dt>Demo sum per place</dt><dd>{GRANT_ETH} ETH</dd>
    <dt>Ground-up if every reported place paid</dt><dd>{grant_sum(n)} ETH · hypothetical, news reports are not a loss survey</dd>
    <dt>Season end</dt><dd>Locked in the escrow. The funder cannot pull committed funds during the season.</dd>
  </dl>
</div></section>

<section class="block" id="loss"><div class="wrap">
  <div class="sec-head"><span class="num">03</span><h2>Loss</h2>
  <p>Three ways to count the same week. The bars are counts of places, not a return period.</p></div>
  <ol class="lossbars">
    <li><span class="lb-lab">If every reported place paid</span><span class="lb-bar" style="width:100%"><span>{n} places · {grant_sum(n)} ETH</span></span><span class="lb-note">Hypothetical. Reports are not claims.</span></li>
    <li><span class="lb-lab">Rainfall-only trigger</span><span class="lb-bar rain" style="width:100%"><span>{rain_n} places · {grant_sum(rain_n)} ETH</span></span><span class="lb-note">Would have fired everywhere. No “did not flood” labels, so no false-alarm count.</span></li>
    <li><span class="lb-lab">This rule · radar and rainfall</span><span class="lb-bar radar" style="width:{modeled_w:.1f}%"><span>{modeled_n} place · {grant_sum(modeled_n)} ETH</span></span><span class="lb-note">The modeled loss. On the testnet as one claim.</span></li>
  </ol>
  <p class="note">Live claim state is read from Sepolia. <span class="live" data-live-zone="{g['modeled'][0]['slug'] if g['modeled'] else ''}"><span class="snap">Reading…</span></span></p>
  <p class="cta"><a class="btn" href="{live_claim}">Open the modeled claim</a></p>
</div></section>

<section class="block alt" id="unmodeled"><div class="wrap">
  <div class="sec-head"><span class="num">04</span><h2>Unmodeled residual</h2>
  <p>In a cat model this is the layer the catalogue missed. Here it is the {unmodeled_n} reported floods the rule did not open. We do not turn that into a return period.</p></div>
  <div class="matrix-wrap"><div>
  <table class="grants"><caption>Reported floods the rule left unmodeled, {grant_sum(unmodeled_n)} ETH of demo exposure</caption>
    <thead><tr><th scope="col">Place</th><th scope="col">Why it stayed out</th><th class="n" scope="col">Demo exposure</th></tr></thead>
    <tbody>{"".join(unmodeled_rows)}</tbody>
  </table></div></div>
  <p class="note">Radar sees open water. Flooding under crops, trees or buildings is invisible to it. A ward box mixes dry and wet land and pulls the fraction down. Three names had no outline we would measure rather than guess.</p>
</div></section>

<section class="block" id="not-a-model"><div class="wrap">
  <div class="sec-head"><span class="num">05</span><h2>What a catastrophe model still has to do</h2>
  <p>This page is the event you would feed the model. It is not the model.</p></div>
  <ul class="limits">
    <li><b>No stochastic catalogue.</b><span>One week. No average annual loss, no occurrence or aggregate exceedance curve, no probable maximum loss, no return period.</span></li>
    <li><b>No vulnerability function.</b><span>We do not convert open-water fraction into damage. The payout is a binary grant.</span></li>
    <li><b>No real exposure file.</b><span>{GRANT_ETH} ETH per place is a demo so the escrow can move. Load your own sums insured.</span></li>
    <li><b>News is not ground-up loss.</b><span>The seven names are places reporters reached. Unknown is not “no flood”.</span></li>
  </ul>
</div></section>"""


def page_responder(build, places, deployment) -> str:
    g = groups(places)

    def card(p, action, cls):
        return f"""<article class="act-card {cls}">
    <p class="who-tag">{escape(action)}</p>
    <h3><a href="{p['page']}">{escape(p['name'])}</a></h3>
    <p class="scale-line">{escape(p['scale'])}</p>
    <p>{escape(p['label_note'])}</p>
    <p class="ws-meta">Source: <a href="{escape(p['label_url'])}">{escape(p['label_source'])}</a></p>
    <p class="live" data-live-zone="{p['slug']}"><span class="snap">{escape(build.snapshot_text(p['slug'], deployment))}</span></p>
  </article>"""

    go = "".join(card(p, "Second signal · radar and rainfall", "go") for p in g["modeled"])
    hold = "".join(card(p, "Rainfall only · radar said no", "hold") for p in g["radar_no"])
    stop = "".join(card(p, "Cannot assess · do not invent a reading", "stop") for p in g["unassessed"])
    return f"""<section class="page-head"><div class="wrap">
  {workspace_nav("responder")}
  <p class="eyebrow">Responder workspace · second signal</p>
  <h1>Move where two instruments agree. Hold where only rainfall signed.</h1>
  <p class="lede">County teams and agencies should not release funds or alerts on one forecast. Radar is a different instrument. Where it could not look, the honest action is to say so, not to treat silence as “no flood”.</p>
  {build.live_bar()}
</div></section>
<section class="block tight"><div class="wrap">
  <div class="action-board">
    <div>
      <h2>{len(g['modeled'])} with a second signal</h2>
      {go or "<p class='note'>None this week.</p>"}
    </div>
    <div>
      <h2>{len(g['radar_no'])} rainfall only</h2>
      {hold or "<p class='note'>None this week.</p>"}
    </div>
    <div>
      <h2>{len(g['unassessed'])} cannot assess</h2>
      {stop or "<p class='note'>None this week.</p>"}
    </div>
  </div>
  <p class="note">Household and village counts in the notes are what the newspapers printed. They are not a survey we ran.</p>
</div></section>"""


def page_data(build, places, counts) -> str:
    g = groups(places)
    n = len(places)
    assessed = len(g["modeled"]) + len(g["radar_no"])
    rain_mm = build.published_total()
    files = [
        ("counts.csv", "Every count on this site"),
        ("radar_fractions.csv", "Radar fraction and pixel counts"),
        ("observations.csv", "What each source signed"),
        ("rule.yaml", "The frozen rule, byte for byte"),
    ]
    downloads = "".join(
        f'<li><a href="data/{name}" download>{name}</a><span>{escape(desc)}</span></li>' for name, desc in files
    )
    return f"""<section class="page-head"><div class="wrap">
  {workspace_nav("data")}
  <p class="eyebrow">Data workspace · ICPAC, Kenya Met</p>
  <h1>An open check on the products you already publish</h1>
  <p class="lede">CHIRPS signed every place because it is one catchment reading. Sentinel-1 could look at {assessed} of {n} places. The rest had no outline we would measure. Compare this against your own stations or your own rainfall field.</p>
</div></section>
<section class="block"><div class="wrap">
  <div class="sec-head"><span class="num">01</span><h2>How each source behaved</h2></div>
  <div class="layers">
    <div class="layer">
      <h3>CHIRPS 2.0 daily</h3>
      <p class="n-lg">{rain_mm:.1f} mm</p>
      <p>Signed {len(g['rainfall'])} of {n}. One upstream catchment, applied everywhere. A millimetre total here is not a gauge total.</p>
    </div>
    <div class="layer">
      <h3>Sentinel-1 RTC</h3>
      <p class="n-lg">{assessed}/{n}</p>
      <p>Assessed {assessed}. Signed {len(g['modeled'])}. Below the line {len(g['radar_no'])}. No geometry {len(g['unassessed'])}: {names(g['unassessed'])}.</p>
    </div>
  </div>
  <div class="matrix-wrap gap-l">
    <div>{build.render_matrix(places)}</div>
    <div>{build.render_misses(counts)}</div>
  </div>
</div></section>
<section class="block alt"><div class="wrap">
  <div class="sec-head"><span class="num">02</span><h2>Take the files and the hash</h2>
  <p>The rule on the chain is a hash of <code>config/rule.yaml</code>. If the bytes change, the hash will not match.</p></div>
  <ul class="downloads">{downloads}</ul>
  <p class="cta"><a class="btn primary" href="backtest.html#check">Hash the rule against the contract</a></p>
</div></section>"""


def page_research(build, places, counts) -> str:
    files = [
        ("counts.csv", "Every count on this site", "backtest/results/counts.csv"),
        ("label_log.csv", "The seven places and the reports that named them", "labels/label_log.csv"),
        ("radar_fractions.csv", "Radar fraction and pixel counts per place", "backtest/checks/radar_fractions.csv"),
        ("observations.csv", "What each source signed, per place", "backtest/observations.csv"),
        ("rule.yaml", "The frozen rule, byte for byte", "config/rule.yaml"),
    ]
    downloads = "".join(
        f'<li><a href="data/{name}" download>{name}</a><span>{escape(desc)} · <code>{src}</code></span></li>'
        for name, desc, src in files
    )
    return f"""<section class="page-head"><div class="wrap">
  {workspace_nav("research")}
  <p class="eyebrow">Research workspace · open method</p>
  <h1>Repeat the count. Do not take the page on trust.</h1>
  <p class="lede">The question is not “how accurate is CHIRPS”. Published studies already disagree on that. The question is: on this week, in these seven named places, where did rainfall and radar agree, and where did they not? The answer is a count.</p>
</div></section>
<section class="block"><div class="wrap">
  <div class="sec-head"><span class="num">01</span><h2>Agreement</h2></div>
  <div class="matrix-wrap">
    <div>{build.render_matrix(places)}</div>
    <div>{build.render_rules(counts)}</div>
  </div>
</div></section>
<section class="block alt"><div class="wrap">
  <div class="sec-head"><span class="num">02</span><h2>Download and reproduce</h2></div>
  <ul class="downloads">{downloads}</ul>
<pre class="cmd"><code>python -m backtest.score
python -m unittest backtest.test_score backtest.pipeline.test_pipeline
python web/build.py</code></pre>
  <p class="cta"><a class="btn" href="backtest.html">Full backtest page</a> <a class="btn" href="backtest.html#check">Hash the rule</a></p>
</div></section>
<section class="block"><div class="wrap">
  <div class="sec-head"><span class="num">03</span><h2>What this cannot tell you</h2></div>
  <ul class="limits">
    <li><b>No “did not flood” labels.</b><span>Without them there are no false alarms, so no precision, and we publish none.</span></li>
    <li><b>One week.</b><span>Nothing here is a skill score for another season.</span></li>
    <li><b>Boxes are not flood outlines.</b><span>A ward box mixes dry and wet land.</span></li>
  </ul>
</div></section>"""


def page_farmer(build, places) -> str:
    cards = []
    for p in places:
        _, outcome, why = build.verdict(p)
        if p["decision"] == "yes" and p["rain"] == "yes":
            word, cls = "Yes. The rule opened a claim.", "yes"
        elif p["decision"] == "abstain":
            word, cls = "We could not look.", "na"
        else:
            word, cls = "No. The rule did not open a claim.", "no"
        cards.append(
            f"""<article class="farmer {cls}" id="{p['slug']}">
    <h2>{escape(p['name'])}</h2>
    <p class="farmer-q">Did this rule say a flood happened here?</p>
    <p class="farmer-a">{escape(word)}</p>
    <p>{escape(why)}</p>
    <p class="ws-meta">{escape(p['label_source'])} reported flooding here. <a href="{p['page']}">See the numbers</a></p>
  </article>"""
        )
    return f"""<section class="page-head farmer-head"><div class="wrap">
  {workspace_nav("farmer")}
  <p class="eyebrow">Farmer view · plain language</p>
  <h1>What the rule said about your place</h1>
  <p class="lede">This page does not pay anyone. It is the reason an insurer or a responder can show you. Many people here use a feature phone; the type is large on purpose.</p>
</div></section>
<section class="block tight"><div class="wrap">
  <div class="farmer-list">
{"".join(cards)}
  </div>
  <p class="note">Nothing on this page moves money. M-PESA in this project is a labelled sandbox. If a claim later pays, that payment is testnet ETH to a placeholder address, not shillings to a phone.</p>
</div></section>"""
