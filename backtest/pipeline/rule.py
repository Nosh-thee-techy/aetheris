"""Read the frozen rule in config/rule.yaml.

The contract's thresholdsHash is keccak256 of that file's bytes. Reported
weeks are not a tuning set. This parser accepts the subset that file uses:
indent, nested maps, lists of scalars, and comments. It does not hash a
re-serialized copy.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULE_PATH = ROOT / "config" / "rule.yaml"


def load_rule(path: Path = RULE_PATH) -> dict:
    """Parse the frozen rule. Missing file is an error, not a default rule."""
    return parse_yaml(path.read_text(encoding="utf-8"))


def rule_id_text(path: Path = RULE_PATH) -> str:
    """The ruleId string stored in the file, before it is hashed."""
    text = load_rule(path)["rule_id"]
    if not isinstance(text, str) or not text:
        raise ValueError("rule_id is empty")
    return text


def rule_id(path: Path = RULE_PATH) -> bytes:
    """bytes32 rule id: keccak256 of the rule_id string."""
    from backtest.pipeline.keccak import keccak256

    return keccak256(rule_id_text(path).encode())


def thresholds_hash(path: Path = RULE_PATH) -> bytes:
    """keccak256 of the rule file bytes. Renaming a key changes the claim."""
    from backtest.pipeline.keccak import keccak256

    return keccak256(path.read_bytes())


def rule_hash(path: Path = RULE_PATH) -> bytes:
    """Older name for thresholds_hash. Same bytes."""
    return thresholds_hash(path)


def parse_yaml(text: str) -> dict:
    """Parse the rule file's YAML subset into dicts, lists, and scalars."""
    lines = _body_lines(text)
    root: dict = {}
    stack: list[tuple[int, dict | list]] = [(-1, root)]
    for index, (indent, line) in enumerate(lines):
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if line.startswith("- "):
            if not isinstance(parent, list):
                raise ValueError(f"list item has no list: {line}")
            parent.append(_scalar(line[2:].strip()))
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.split(" #", 1)[0].strip()
        if not key or not isinstance(parent, dict):
            raise ValueError(f"bad rule line: {line}")
        if rest == "":
            nxt = lines[index + 1][1] if index + 1 < len(lines) else ""
            child: dict | list = [] if nxt.startswith("- ") else {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _scalar(rest)
    return root


def _body_lines(text: str) -> list[tuple[int, str]]:
    lines = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw.startswith(" ") and not raw.startswith("  "):
            raise ValueError("rule indent must be two spaces")
        lines.append((len(raw) - len(raw.lstrip(" ")), stripped))
    return lines


def _scalar(value: str):
    """Bool, number, or string. Quoted text is returned without the quotes."""
    if value in ("true", "false"):
        return value == "true"
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    try:
        if any(mark in value for mark in (".", "e", "E")):
            return float(value)
        return int(value)
    except ValueError:
        return value
