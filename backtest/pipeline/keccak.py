"""Keccak-256. Ethereum uses this, not NIST SHA3-256."""

from __future__ import annotations

_ROTATION = (
    (0, 36, 3, 41, 18),
    (1, 44, 10, 45, 2),
    (62, 6, 43, 15, 61),
    (28, 55, 25, 21, 56),
    (27, 20, 39, 8, 14),
)
_RC = (
    0x0000000000000001,
    0x0000000000008082,
    0x800000000000808A,
    0x8000000080008000,
    0x000000000000808B,
    0x0000000080000001,
    0x8000000080008081,
    0x8000000000008009,
    0x000000000000008A,
    0x0000000000000088,
    0x0000000080008009,
    0x000000008000000A,
    0x000000008000808B,
    0x800000000000008B,
    0x8000000000008089,
    0x8000000000008003,
    0x8000000000008002,
    0x8000000000000080,
    0x000000000000800A,
    0x800000008000000A,
    0x8000000080008081,
    0x8000000000008080,
    0x0000000080000001,
    0x8000000080008008,
)
_MASK = (1 << 64) - 1


def _rotl(value: int, shift: int) -> int:
    if shift == 0:
        return value
    return ((value << shift) | (value >> (64 - shift))) & _MASK


def _permute(lanes: list[list[int]]) -> None:
    for round_index in range(24):
        column = [lanes[x][0] ^ lanes[x][1] ^ lanes[x][2] ^ lanes[x][3] ^ lanes[x][4] for x in range(5)]
        for x in range(5):
            mixed = column[(x - 1) % 5] ^ _rotl(column[(x + 1) % 5], 1)
            for y in range(5):
                lanes[x][y] ^= mixed
        rotated = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                rotated[y][(2 * x + 3 * y) % 5] = _rotl(lanes[x][y], _ROTATION[x][y])
        for x in range(5):
            for y in range(5):
                lanes[x][y] = rotated[x][y] ^ ((~rotated[(x + 1) % 5][y]) & rotated[(x + 2) % 5][y]) & _MASK
        lanes[0][0] ^= _RC[round_index]


def keccak256(data: bytes) -> bytes:
    rate = 136
    lanes = [[0] * 5 for _ in range(5)]
    offset = 0
    while offset + rate <= len(data):
        _xor_block(lanes, data[offset : offset + rate])
        _permute(lanes)
        offset += rate
    tail = bytearray(rate)
    tail[: len(data) - offset] = data[offset:]
    tail[len(data) - offset] ^= 0x01
    tail[-1] ^= 0x80
    _xor_block(lanes, tail)
    _permute(lanes)
    out = bytearray(32)
    for index in range(32):
        x = (index // 8) % 5
        y = index // 40
        out[index] = (lanes[x][y] >> (8 * (index % 8))) & 0xFF
    return bytes(out)


def _xor_block(lanes: list[list[int]], block: bytes) -> None:
    for index, byte in enumerate(block):
        x = (index // 8) % 5
        y = index // 40
        lanes[x][y] ^= byte << (8 * (index % 8))
