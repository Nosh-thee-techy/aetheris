# Aetheris

Parametric flood payouts for the Nyando basin, western Kenya. A payout is allowed only when the radar attester sees open water and at least one corroborating attester agrees. Anyone can challenge that decision before it finalizes. The headline result is a backtest: where this rule would have paid, paid wrongly, or missed.

The chain gates the decision. It does not send the money. `PayoutEscrow` can release testnet ETH to a beneficiary only after a trigger is `Finalized`, and only once for that zone-week. A Daraja mirror in `watcher/` is labeled SANDBOX and does not move KES.

This repository is the build. The rule in `config/rule.yaml` is frozen as of 12 October 2026. `thresholdsHash` is keccak256 of that file. The evidence is in `docs/checks.md`. Do not change the catchment, the lag, or the thresholds after the label log is filled. The 4–6 May 2024 week was not used to fit them. There is no second labeled season, and neighboring zones were not held out, because they share the same flood.

## The rule

Radar is mandatory. Rainfall corroborates. Rainfall alone cannot open a trigger.

| Attester | Role | Fires when |
|---|---|---|
| Sentinel-1 radar | Hazard | Share of a zone's land pixels that look like new open water is above 0.05, using the untuned -16 dB prior, with permanent water removed |
| CHIRPS rainfall | Corroboration | The 3-day sum of rain on the Nandi–Tinderet and Kericho–Mau boxes reaches 40 mm, ending on the radar date |

A ground attester is not in this build. A simulated ground signature would look like independence we do not have.

The report scene is the Sentinel-1A pass on 6 May 2024. Rainfall is read on the headwaters, not on the flooded zone. Daily CHIRPS in the April 2020 check moved with the plain on the same day, so the lag is zero. A high lake with little new rain is still a miss. The 40 mm line is a round prior, not a fitted cutoff.

## What a signature means

The trigger id is:

```text
keccak256(zoneId, eventWeek, ruleId, thresholdsHash)
```

`ruleId` is keccak256 of `nyando-open-water-v1`. `thresholdsHash` is keccak256 of `config/rule.yaml`. Both are fixed when the contract is deployed. Signing means "this payout rule fired." An attester who does not agree does not sign. Silence is a no. Each signer stores an evidence hash for the scene or raster they used. A second signature from the same attester reverts.

## What the contract enforces

`contracts/src/FloodTrigger.sol`

1. **Attest.** The radar key or a registered corroborator posts a bond and an evidence hash. One signature per attester.
2. **Quorum.** The challenge window opens only after the radar attester and at least one corroborator have signed.
3. **Challenge.** Anyone can stake during the window. The trigger freezes.
4. **Resolve.** The resolver can only uphold or reject a live challenge. Uphold finalizes the trigger and gives the challenger's stake to the pool. Reject cancels the trigger and gives the attester bonds to the challenger.
5. **Expiry.** If the resolver does not act before the resolve deadline, anyone can expire the challenge. The trigger finalizes, and the challenger's stake is returned. A silent resolver cannot block a payout.
6. **Unchallenged finalize.** If the window closes with no challenge, anyone can finalize. Bonds are returned.

Bonds and stakes are pulled with `withdraw()`. The resolver cannot be an attester, cannot open a trigger, and cannot change an evidence hash.

These are the demo limits, and they stay visible:

- The resolver is one named key, not a 2-of-3 and not a vote. `IFloodResolver` is the one function a later vote would call.
- Expiry fails toward payout. The pool's protection is the bond and the challenge window.
- Dispute resolution is the weakest part of the design.
- The contracts are unaudited and meant for a testnet.

## The backtest

`backtest/score.py` scores attester decisions against a label log. The pre-committed run is the 2024 long rains, week `2024-05-04/2024-05-06`, and the seven zones in `config/rule.yaml`. The metrics are counts: labeled zone-weeks, flood labels, hits, misses, and false triggers.

- Labels are `flood`, `no_flood`, or `unknown`. A blank label is `unknown`.
- Unknown zone-weeks are excluded from the hit, miss, and false-trigger counts. A trigger that fires on an unknown label is counted as `fired_unknown`.
- The report is counts. It does not publish an accuracy percentage.
- The agreement table counts `both_yes`, `radar_only`, `rainfall_only`, `both_no`, and abstentions. Disagreements are the only rows where rainfall changes the outcome.
- The same week is also scored as radar only, radar plus rainfall, and rainfall only.
- Misses on flooded zones are split into `no_scene`, `below_threshold`, `uncorroborated`, `rainfall_gap`, and `no_geometry`. A missing place outline is `no_geometry`. A missing satellite pass is `no_scene`.
- Open-water thresholding does not see flood under vegetation. That uncovered hazard is stated beside the table. It is not a miss bucket the scorer can see.

Hold out a whole other season if you tune anything. Neighboring zones share the same flood, so a spatial split leaks. With one season, leave the prior thresholds untouched and say the run is untuned.

## Honest limits

- Radar sees open water. It misses flood under vegetation and inside buildings, and Sentinel-1A's 2024 revisit is twelve days. A week with no pass is a miss (`no_scene`).
- Rainfall and radar both look at the same storm. They are not independent witnesses. On this week they disagree on 3 of 4 decided pairs, because rainfall is yes everywhere and radar is yes in one place.
- CHIRPS is the rainfall product. IMERG is not connected. Satellite rainfall products overestimate light rain and underestimate heavy rain. The lag is 0 days, from the April 2020 check. A high lake with little new rain is still a miss.
- The resolver in this demo is one named key, not a committee. Expiry leaves the attester result standing.
- One season is indicative. The label log is news reports, which favour places reporters and rescuers could reach.
- Payout in `watcher/` is a Daraja SANDBOX record. It does not send money. The escrow, when funded, pays testnet ETH to the committed beneficiary address and nothing else.

## Priority

**Now:** the frozen rule is `config/rule.yaml`. The metric log is `labels/label_log.csv`. Rainfall for 4–6 May 2024 is one catchment decision, 56.7 mm, copied onto each labeled zone. Radar fractions for the 6 May scene are in `backtest/checks/radar_fractions.csv`. The agreement table is `docs/agreement.md`. The quorum fires for Kabonyo Kanyagwal only. There are no dry labels, so that table does not test a false trigger.

**In the same contract, drop these first if the backtest slips:** attester bonds, the uphold-or-reject resolver, and challenge expiry. Those three are already in `FloodTrigger`. `PayoutEscrow` pays a committed beneficiary after `Finalized`.

**Done:** both contracts are deployed on Sepolia (see below), with one claim open: Kabonyo Kanyagwal. The radar and rainfall jobs in `backtest/pipeline` decide whether to sign. They do not send transactions yet; the deploy script submitted the demo claim with the same two keys. The site in `web/` reads the contracts live in the browser.

## Deployed on Sepolia

Testnet only. Unaudited. Record: `web/data/deployment.json`.

| | |
|---|---|
| FloodTrigger | [`0xFE35E6F742e7bdD2864AB753035F82047399E3D2`](https://sepolia.etherscan.io/address/0xFE35E6F742e7bdD2864AB753035F82047399E3D2) |
| PayoutEscrow | [`0x70A0c3A7Fbd36d9E822CC11c19a7fD5B7b98A7d1`](https://sepolia.etherscan.io/address/0x70A0c3A7Fbd36d9E822CC11c19a7fD5B7b98A7d1) |

- The claim for Kabonyo Kanyagwal, 4–6 May 2024, has both required signatures. Its 24-hour challenge window closes 2026-10-24 06:31 UTC. Anyone can challenge until then, then anyone can finalize, then anyone can release.
- The six other places have no claim. The rule did not fire there, and the contract holds nothing for them.
- The seven payout beneficiaries are placeholder addresses derived from a hash. Nobody holds a key for them. A release credits them correctly and the ETH stays there.
- `thresholdsHash` on the chain equals keccak256 of `config/rule.yaml` **as stored in git**. `.gitattributes` pins that file's bytes, line endings included. Check it yourself on the Backtest page, or:

```powershell
node -e "const {keccak256}=require('./contracts/tools/node_modules/ethers');console.log(keccak256(require('fs').readFileSync('config/rule.yaml')))"
```

Expected: `0x1c6711d40c3742d19b3da4368c97a56e8777cf19c845e2ec5b2608831f232d4b`.

**Not in this build:** USSD, a simulated ground attester, and a resolver multisig. Ground readings are not labels.

## Repo

```text
config/rule.yaml   frozen rule, hashed as thresholdsHash
labels/label_log.csv  flood / no_flood / unknown
contracts/         FloodTrigger, PayoutEscrow, Foundry tests, deploy script
contracts/tools/   node scripts: compile, rehearse (local chain), deploy_testnet, referee
backtest/          scorer, results/counts.csv, scene and rainfall checks
watcher/           Daraja SANDBOX mirror, no KES moved
web/               the site: build.py generates the pages, app.js reads the chain
web/data/          deployment record and copies of the data the pages cite
docs/agreement.md  scored agreement table
.github/           tests on push
```

`backtest/pipeline` is the two attester jobs. Rainfall reads CHIRPS on Earth Engine for a new scene and uses the published 56.7 mm for 6 May 2024. Radar signs only when the frozen RTC fraction clears. Each attester has its own key. The resolver key is not an attester.

## Setup

Clone with the Foundry test library:

```powershell
git clone --recurse-submodules https://github.com/Nosh-thee-techy/aetheris.git
```

Contract tests need [Foundry](https://book.getfoundry.sh/getting-started/installation):

```powershell
forge test --root contracts
```

Backtest tests use the Python standard library:

```powershell
python -m unittest backtest.test_score backtest.test_week backtest.pipeline.test_pipeline watcher.test_mirror web.test_build web.test_server
python -m backtest.week --recipe
python -m backtest.week
```

`python -m backtest.week` is the documented job: print the recipe (scene → radar CSV → rainfall rows → score), then score the published files. `python -m backtest.score` is the scorer alone. Both read `labels/label_log.csv` and write `backtest/results/counts.csv`, including every miss reason. The website reads those CSVs. It does not download a GeoTIFF. The notebook `backtest/agreement.ipynb` runs the same scorer. A second week is allowed only if `config/rule.yaml` is unchanged. There is no gauge file; do not stub stations.

### The site

```powershell
cd app
npm install
npm run build              # writes web/spa — landing, enter, desks
cd ..
python web/build.py        # writes method, claims, backtest and chain-config.js
python web/server.py       # http://127.0.0.1:8765/
```

The visitor site also deploys on Vercel (`vercel.json`): Vite writes `web/spa`, `web/prepare_spa.py` copies `/media` and `/data`, and `/api/*` is the same desk JSON. No keys go up.

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/). The whole visitor site is a Vite app: landing, enter, method, claims, backtest, and the desks. Enter is a labelled gate: pick a role, no password, no accounts, no machine learning. Old `.html` addresses still open the same pages. `GET /api/desk` is readable without a session. The API repeats the same CSVs the generator already uses. It does not invent radar yes/no. Chain state on the claims pages is the deploy snapshot, labelled as a snapshot. `GET /api/me` is `200` with `{ok:false}` when nobody has entered.

Pages: Home, Enter, Method, Claims (which ends with the payout escrow and withdrawals), one page per place, Backtest, and a desk for each stakeholder (insurer, reinsurer event-loss, responder, data desk, research, farmer view). The reinsurer page is one named event layered like a catastrophe model. It is not a stochastic catalogue. Vulnerability is an indicative JRC depth-damage layer: waist-high at Ahero, converted to 0.9 m, labelled adapted or assumption. Radar fraction is not used as depth. `build.py` computes the claim ids and evidence hashes and **fails the build** if they disagree with `web/data/deployment.json`. `app.js` reads Sepolia in the browser and holds no keys. Writes (challenge, finalize, release, withdraw) go through the visitor's own wallet. The only library is a vendored copy of ethers 6.17.0 in `web/vendor/`. Nothing loads from a CDN.

### The contract tools

These were run on Node 24. `forge test` remains the contract test suite. The rehearsal is a second, independent check on a local in-process chain.

```powershell
cd contracts/tools
npm install
node rehearse.mjs                       # 26 checks on a local chain; no network, no funds
node deploy_testnet.mjs --check         # balances and readiness; sends nothing
node referee.mjs status kabonyo-kanyagwal
node referee.mjs finalize kabonyo-kanyagwal   # after the window; also: release, expire, uphold, reject
```

`uphold` and `reject` work only with the referee key. That key is the deployer key in `.env`. Never paste it into a browser wallet.

Deploy reads `RULE_ID`, `THRESHOLDS_HASH`, `RESOLVER`, `RADAR_ATTESTER`, `RAINFALL_ATTESTER`, `POOL`, `FUNDER`, and `SEASON_END` from the environment. `python -m backtest.pipeline.keys` writes those to `.env` and will not overwrite a file that is already there. The resolver key deploys. It is not an attester. `THRESHOLDS_HASH` is keccak256 of `config/rule.yaml`. Copy `.env` into the shell, fund `RESOLVER` on Sepolia, then:

```powershell
forge script script/Deploy.s.sol --root contracts --rpc-url $env:SEPOLIA_RPC_URL --private-key $env:DEPLOYER_PRIVATE_KEY --broadcast
```

The person building this is a student, recorded in `docs/checks.md` on 19 October 2026. The Devpost badge and the written rules still disagree, so a second person has to pass the same reading. The Devpost deadline to plan against is 25 October 2026 at 5:00pm Moscow time.
