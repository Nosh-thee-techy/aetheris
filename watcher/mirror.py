"""Record a released escrow event for a Daraja SANDBOX off-ramp.

This does not call Safaricom. It does not send KES. A later sandbox client
can read the record. Every record is labeled SANDBOX.
"""

from __future__ import annotations


def mirror_release(trigger_id: str, zone: str, amount_wei: int) -> dict:
    """Copy one finalized release into a sandbox record. Amount stays in wei."""
    if not trigger_id or not zone:
        raise ValueError("a sandbox record needs a trigger and a zone")
    if amount_wei < 0:
        raise ValueError("amount cannot be negative")
    return {
        "label": "SANDBOX",
        "rail": "daraja-sandbox",
        "moved_kes": False,
        "trigger_id": trigger_id,
        "zone": zone,
        "amount_wei": amount_wei,
    }
