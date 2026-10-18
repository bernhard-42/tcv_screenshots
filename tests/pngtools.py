"""Minimal PNG reading and writing for the tests, standard library only.

Handles what Chromium's canvas produces: 8 bit, non-interlaced, gray, RGB or RGBA.
"""

import struct
import zlib

_CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}


def _chunks(data: bytes):
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    pos = 8
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        yield kind, data[pos + 8 : pos + 8 + length]
        pos += 12 + length


def decode(data: bytes) -> tuple[int, int, int, bytes]:
    """Width, height, channels and the raw pixel bytes of a PNG."""
    idat = b""
    for kind, body in _chunks(data):
        if kind == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", body)
            assert depth == 8 and interlace == 0, "only 8 bit non-interlaced PNGs"
            channels = _CHANNELS[color]
        elif kind == b"IDAT":
            idat += body
    raw = zlib.decompress(idat)
    stride = width * channels
    out = bytearray()
    prev = bytearray(stride)
    pos = 0
    for _ in range(height):
        kind = raw[pos]
        line = bytearray(raw[pos + 1 : pos + 1 + stride])
        pos += 1 + stride
        for i in range(stride):
            left = line[i - channels] if i >= channels else 0
            up = prev[i]
            up_left = prev[i - channels] if i >= channels else 0
            if kind == 1:
                line[i] = (line[i] + left) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + up) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 0xFF
            elif kind == 4:
                p = left + up - up_left
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - up_left)
                pred = left if pa <= pb and pa <= pc else (up if pb <= pc else up_left)
                line[i] = (line[i] + pred) & 0xFF
        out += line
        prev = line
    return width, height, channels, bytes(out)


def max_difference(a: bytes, b: bytes) -> int:
    """Largest difference of any channel of any pixel of two PNGs of equal size."""
    wa, ha, ca, pa = decode(a)
    wb, hb, cb, pb = decode(b)
    assert (wa, ha, ca) == (wb, hb, cb), f"{wa}x{ha}x{ca} vs {wb}x{hb}x{cb}"
    return max(abs(x - y) for x, y in zip(pa, pb))


def encode(width: int, height: int, rgba: bytes) -> bytes:
    """An RGBA PNG without filtering, for tests that need a known image."""
    raw = b"".join(b"\x00" + rgba[y * width * 4 : (y + 1) * width * 4] for y in range(height))

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
