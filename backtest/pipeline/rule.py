"""Read the frozen rule. Do not substitute a second set of thresholds."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULE_PATH = ROOT / "backtest" / "rule.toml"


def load_rule(path: Path = RULE_PATH) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def rule_hash(path: Path = RULE_PATH) -> bytes:
    from backtest.pipeline.keccak import keccak256

    return keccak256(path.read_bytes())
