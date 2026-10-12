# Aetheris

Parametric flood payouts for the Nyando basin, western Kenya. A payout is allowed only when the radar attester sees open water and at least one corroborating attester agrees. Anyone can challenge that decision before it finalizes. The headline result is a backtest: where this rule would have paid, paid wrongly, or missed.

The chain gates the decision. It does not send the money. A watcher may deliver a finalized trigger through the M-PESA sandbox later. Until a trigger is `Finalized`, nothing is payable.

This repository is the build. The rule in `backtest/rule.toml` is frozen as of 12 October 2026. The evidence is in `docs/checks.md`. Do not change the catchment, the lag, or the thresholds after the label log is filled.

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
keccak256(zoneId, eventStart, eventEnd, ruleHash)
```

`ruleHash` is fixed when the contract is deployed. Signing means "this frozen rule fired for this zone and window." An attester who does not agree does not sign. Silence is a no. Each signer also stores an evidence hash for the scene or raster they used.

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

- The resolver is one named key, not a vote.
- Expiry fails toward payout. The pool's protection is the bond and the challenge window.
- Dispute resolution is the weakest part of the design. Replacing the named key with a vote is later work.
- The contract is unaudited and meant for a testnet.

## The backtest

`backtest/score.py` scores attester decisions against a label log.

- Labels are `flooded`, `not_flooded`, or `unknown`. A blank label is `unknown`.
- Unknown zone-weeks are excluded from precision, recall, and basis risk. A trigger that fires on an unknown label is counted as `fired_unknown`, not as a success.
- The agreement table counts `both_yes`, `radar_only`, `rainfall_only`, `both_no`, and abstentions. Disagreements are the only rows where rainfall changes the outcome.
- Misses on flooded zones are split into `no_scene`, `below_threshold`, `uncorroborated`, and `rainfall_gap`.
- Open-water thresholding does not see flood under vegetation. That uncovered hazard is stated beside the table. It is not a third miss bucket the scorer can see.

Hold out a whole other season if you tune anything. Neighboring zones share the same flood, so a spatial split leaks. With one season, leave the prior thresholds untouched and say the run is untuned.

## Honest limits

- Sentinel-1 and CHIRPS are both remote sensing of the same storm. They are not independent witnesses. The agreement table is how we show that.
- Radar is mandatory, so a missing Sentinel-1 pass is a missed payout. Report passes that do not exist.
- CHIRPS blends satellite estimates with gauges.
- A rainfall rule, including an upstream catchment, still misses backwater flooding from the lake.
- One season is indicative. Publish the counts, not an accuracy claim.
- M-PESA, when it exists here, is a sandbox. The watcher does not decide who is owed. That policy will be a file whose hash is fixed at deploy.

## Priority

**Now:** radar flooded fraction for the labeled places on the 6 May 2024 scene, then the agreement table.

The label log for 4–6 May 2024 is in `backtest/labels.csv`. It contains only places a report named. See `docs/labels.md`. Rainfall for that event is one catchment decision, copied onto each labeled zone. Radar fractions are not measured yet, so the agreement table is not published.

**In the same contract, drop these first if the backtest slips:** attester bonds, the uphold-or-reject resolver, and challenge expiry. Those three are already in `FloodTrigger`.

**Later:** testnet deploy with separate keys, radar pipeline, rainfall pipeline, sandbox watcher, dashboard.

**Not in this build:** USSD, a simulated ground attester, a resolver multisig, and an on-chain beneficiary table.

## Repo

```text
contracts/     FloodTrigger, Foundry tests, deploy script
backtest/      frozen rule, label log, scorer, scene and rainfall checks
docs/checks.md eligibility, the 6 May 2024 scene, and the rainfall result
docs/labels.md  places named as flooded on 4–6 May 2024
.github/       tests on push
```

Attester pipelines, the watcher, and the dashboard are not in the tree yet.

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
python -m unittest backtest.test_score
```

Deploy reads `RULE_HASH`, `RESOLVER`, `RADAR_ATTESTER`, `RAINFALL_ATTESTER`, and `POOL` from the environment. Do not deploy until `backtest/rule.toml` is frozen and `RULE_HASH` is the hash of that file.

Eligibility is still open. The Devpost badge says students only. The written rules also list faculty, startups, and professionals. See `docs/checks.md` before treating a submission slot as safe. The Devpost deadline to plan against is 25 October 2026 at 5:00pm Moscow time.
