// Ids shared with backtest/pipeline/ids.py. Both sides must hash the same strings,
// or a signature would commit to a claim nobody else can reproduce.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { keccak256, toUtf8Bytes } from "ethers";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
export const RULE_FILE = join(ROOT, "config", "rule.yaml");

/** keccak256 of a place slug, e.g. "kabonyo-kanyagwal". */
export const zoneId = (slug) => keccak256(toUtf8Bytes(slug));

/** keccak256 of a "start/end" week string, e.g. "2024-05-04/2024-05-06". */
export const weekId = (week) => keccak256(toUtf8Bytes(week));

/** keccak256 of the rule_id string inside config/rule.yaml. */
export function ruleId() {
  const match = readFileSync(RULE_FILE, "utf8").match(/^rule_id:\s*(\S+)\s*$/m);
  if (!match) throw new Error("rule_id missing from config/rule.yaml");
  return keccak256(toUtf8Bytes(match[1]));
}

/** keccak256 of the rule file's exact bytes. Do not reformat the file. */
export const thresholdsHash = () => keccak256(readFileSync(RULE_FILE));

/** Evidence the radar attester commits to: the scene it measured. */
export const evidenceRadar = (itemId) => keccak256(toUtf8Bytes(`sentinel-1-rtc:${itemId}`));

/** Evidence the rainfall attester commits to: the CHIRPS window it summed. */
export const evidenceRainfall = (first, last) =>
  keccak256(toUtf8Bytes(`UCSB-CHG/CHIRPS/DAILY:${first}:${last}`));

export const SCENE_ITEM = "S1A_IW_GRDH_1SDV_20240506T155655_20240506T155720_053752_068803_rtc";
export const WEEK = "2024-05-04/2024-05-06";
