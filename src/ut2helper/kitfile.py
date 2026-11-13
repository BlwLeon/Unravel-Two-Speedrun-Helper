"""Reader/writer for Unravel Two ".kit" archives (Coldwood / PhyreEngine based).

Layout (reverse engineered, little endian):

    <name>.kit        index file
        0x00  "kit!" magic
        0x18  u32  number of entries
        0x1C  u32  number of data parts (<name>.kit.0, .1, ...)
        ...   hash table (not needed here)
        end   entries, 56 bytes each, stored backwards from the end of the file,
              followed by the 4 byte footer "!tik"

    entry (56 bytes):
        u32  name hash
        u32  type            (1/2 = stored, 9/10 = LZ4 chunks)
        u16  part number
        u48  offset inside the part
        u64  stored size
        u64  unpacked size
        20b  SHA1 of the unpacked data
        u32  zero

    compressed data = sequence of [u32 size][LZ4 block], each block <= 64 KiB
    unpacked; blocks may reference the previous block (linked LZ4 stream).
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path

ENTRY_SIZE = 56
BLOCK_SIZE = 65536


class KitError(Exception):
    pass


@dataclass
class Entry:
    pos: int          # byte position of the entry inside the index file
    name_hash: int
    type: int
    part: int
    offset: int
    stored_size: int
    unpacked_size: int
    sha1: bytes


class KitIndex:
    def __init__(self, data: bytes):
        if data[:4] != b"kit!":
            raise KitError("not a kit index (bad magic)")
        self.data = bytearray(data)
        self.count, self.parts = struct.unpack_from("<II", data, 0x18)
        self.entries: dict[int, Entry] = {}
        pos = len(data) - 4 - ENTRY_SIZE
        for _ in range(self.count):
            h, t, part = struct.unpack_from("<IIH", data, pos)
            off = int.from_bytes(data[pos + 10:pos + 16], "little")
            cs, us = struct.unpack_from("<QQ", data, pos + 16)
            sha = bytes(data[pos + 32:pos + 52])
            self.entries[h] = Entry(pos, h, t, part, off, cs, us, sha)
            pos -= ENTRY_SIZE

    @classmethod
    def load(cls, path: Path) -> "KitIndex":
        return cls(Path(path).read_bytes())

    def entry(self, name_hash: int) -> Entry:
        try:
            return self.entries[name_hash]
        except KeyError:
            raise KitError(f"entry {name_hash:08x} not found") from None

    def set_entry(self, e: Entry, part: int, offset: int, stored: int, unpacked: int, sha1: bytes) -> None:
        struct.pack_into("<H", self.data, e.pos + 8, part)
        self.data[e.pos + 10:e.pos + 16] = offset.to_bytes(6, "little")
        struct.pack_into("<QQ", self.data, e.pos + 16, stored, unpacked)
        self.data[e.pos + 32:e.pos + 52] = sha1

    def to_bytes(self) -> bytes:
        return bytes(self.data)


# --------------------------------------------------------------------------- LZ4

def lz4_decompress_block(src: bytes, out: bytearray) -> None:
    """Decode one LZ4 block and append to ``out`` (``out`` acts as dictionary)."""
    i, n = 0, len(src)
    while i < n:
        token = src[i]
        i += 1
        lit = token >> 4
        if lit == 15:
            while True:
                b = src[i]
                i += 1
                lit += b
                if b != 255:
                    break
        out += src[i:i + lit]
        i += lit
        if i >= n:
            break
        off = src[i] | (src[i + 1] << 8)
        i += 2
        mlen = token & 15
        if mlen == 15:
            while True:
                b = src[i]
                i += 1
                mlen += b
                if b != 255:
                    break
        mlen += 4
        start = len(out) - off
        if off <= 0 or start < 0:
            raise KitError("corrupt LZ4 data")
        if off >= mlen:
            out += out[start:start + mlen]
        else:
            for k in range(mlen):
                out.append(out[start + k])


def lz4_literal_block(data: bytes) -> bytes:
    """Encode ``data`` as a valid LZ4 block that only contains literals."""
    n = len(data)
    head = bytearray()
    if n >= 15:
        head.append(0xF0)
        rest = n - 15
        while rest >= 255:
            head.append(255)
            rest -= 255
        head.append(rest)
    else:
        head.append(n << 4)
    return bytes(head) + data


def pack_chunks(data: bytes) -> bytes:
    out = bytearray()
    for i in range(0, len(data), BLOCK_SIZE):
        block = lz4_literal_block(data[i:i + BLOCK_SIZE])
        out += struct.pack("<I", len(block)) + block
    return bytes(out)


def unpack_chunks(raw: bytes, unpacked_size: int) -> bytes:
    out = bytearray()
    pos = 0
    while pos + 4 <= len(raw) and len(out) < unpacked_size:
        size = struct.unpack_from("<I", raw, pos)[0]
        lz4_decompress_block(raw[pos + 4:pos + 4 + size], out)
        pos += 4 + size
    if len(out) != unpacked_size:
        raise KitError("unpacked size mismatch")
    return bytes(out)


# --------------------------------------------------------------------------- helpers

def read_entry(index: KitIndex, part_paths: dict[int, Path], name_hash: int) -> bytes:
    e = index.entry(name_hash)
    with open(part_paths[e.part], "rb") as f:
        f.seek(e.offset)
        raw = f.read(e.stored_size)
    if e.stored_size == e.unpacked_size:
        data = raw
    else:
        data = unpack_chunks(raw, e.unpacked_size)
    if hashlib.sha1(data).digest() != e.sha1:
        raise KitError(f"checksum mismatch for entry {name_hash:08x}")
    return data


def build_patched(index_bytes: bytes, last_part: bytes, replacements: dict[int, bytes]) -> tuple[bytes, bytes]:
    """Return (new index, new last part) with ``replacements`` appended to the last part.

    The original data stays untouched; the index entries are pointed at the new copies.
    """
    index = KitIndex(index_bytes)
    last = index.parts - 1
    part = bytearray(last_part)
    for name_hash, data in replacements.items():
        e = index.entry(name_hash)
        while len(part) % 16:
            part.append(0)
        offset = len(part)
        packed = pack_chunks(data)
        part += packed
        index.set_entry(e, last, offset, len(packed), len(data), hashlib.sha1(data).digest())
    return index.to_bytes(), bytes(part)
