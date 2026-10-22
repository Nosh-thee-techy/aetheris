"""Write five testnet role keys. The resolver deploys. It is not an attester.

Secrets go to .env at the repo root. That file is gitignored. Running this
again leaves an existing file alone.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backtest.pipeline.rule import ROOT, rule_hash, rule_id

ENV_PATH = ROOT / ".env"
ROLES = ("RESOLVER", "RADAR_ATTESTER", "RAINFALL_ATTESTER", "POOL", "FUNDER")
RPC_URL = "https://ethereum-sepolia-rpc.publicnode.com"


def _accounts():
    try:
        from eth_account import Account
    except ImportError as error:
        raise SystemExit(
            "pip install eth-account, then run python -m backtest.pipeline.keys"
        ) from error
    created = []
    for _ in ROLES:
        created.append(Account.create())
    addresses = {account.address for account in created}
    if len(addresses) != len(ROLES):
        raise SystemExit("key generation collided; run it again")
    return created


def render(accounts) -> str:
    hashed = "0x" + rule_hash().hex()
    season_end = int(datetime(2026, 12, 31, tzinfo=timezone.utc).timestamp())
    resolver, radar, rainfall, pool, funder = accounts
    lines = [
        f"SEPOLIA_RPC_URL={RPC_URL}",
        f"RULE_ID=0x{rule_id().hex()}",
        f"THRESHOLDS_HASH={hashed}",
        "# Demo season end. Unspent escrow can be reclaimed only after this unix time.",
        f"SEASON_END={season_end}",
        "# The resolver deploys. The contract rejects a resolver who is also an attester.",
        f"DEPLOYER_PRIVATE_KEY=0x{resolver.key.hex()}",
        f"RESOLVER={resolver.address}",
        f"RADAR_ATTESTER={radar.address}",
        f"RADAR_ATTESTER_PRIVATE_KEY=0x{radar.key.hex()}",
        f"RAINFALL_ATTESTER={rainfall.address}",
        f"RAINFALL_ATTESTER_PRIVATE_KEY=0x{rainfall.key.hex()}",
        f"POOL={pool.address}",
        f"POOL_PRIVATE_KEY=0x{pool.key.hex()}",
        f"FUNDER={funder.address}",
        f"FUNDER_PRIVATE_KEY=0x{funder.key.hex()}",
        "",
    ]
    return "\n".join(lines)


def write_env(path: Path = ENV_PATH) -> Path:
    if path.exists():
        return path
    path.write_text(render(_accounts()), encoding="utf-8")
    return path


def addresses(path: Path = ENV_PATH) -> dict[str, str]:
    found = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in ("RESOLVER", "RADAR_ATTESTER", "RAINFALL_ATTESTER", "POOL", "FUNDER", "RULE_ID", "THRESHOLDS_HASH"):
            found[key] = value
    return found


def main() -> None:
    path = write_env()
    print(path)
    for key, value in addresses(path).items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
