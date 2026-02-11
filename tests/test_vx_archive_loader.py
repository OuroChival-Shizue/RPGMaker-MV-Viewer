from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from viewer.data_loader import DataLoader


def _u32(v: int) -> int:
    return v & 0xFFFFFFFF


def _crypt_payload(raw: bytes, data_key: int) -> bytes:
    data = bytearray(raw)
    groups = len(data) // 4
    key = data_key
    for i in range(groups):
        base = i * 4
        data[base] ^= (key >> 0) & 0xFF
        data[base + 1] ^= (key >> 8) & 0xFF
        data[base + 2] ^= (key >> 16) & 0xFF
        data[base + 3] ^= (key >> 24) & 0xFF
        key = _u32(key * 7 + 3)
    pos = groups * 4
    while pos < len(data):
        data[pos] ^= (key >> (8 * (pos % 4))) & 0xFF
        pos += 1
    return bytes(data)


def _build_rgss3a_single_entry(path: Path, *, name: str, payload: bytes) -> None:
    key0 = 3580
    magic = _u32(key0 * 9 + 3)
    data_key = 0x12345678

    enc_payload = _crypt_payload(payload, data_key)
    name_bytes = name.encode("utf-8")
    key_bytes = struct.pack("<I", magic)
    name_enc = bytes(b ^ key_bytes[i % 4] for i, b in enumerate(name_bytes))

    header = b"RGSSAD" + b"\x00" + b"\x03" + struct.pack("<I", key0)
    entry_size = 16 + len(name_enc)
    offset = len(header) + entry_size + 16
    index = struct.pack(
        "<IIII",
        offset ^ magic,
        len(enc_payload) ^ magic,
        data_key ^ magic,
        len(name_enc) ^ magic,
    ) + name_enc
    terminator = struct.pack("<IIII", magic, 0, 0, 0)
    path.write_bytes(header + index + terminator + enc_payload)


class VxArchiveLoaderTest(unittest.TestCase):
    def test_can_load_mapinfos_from_rgss3a(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "Data"
            data_dir.mkdir(parents=True)
            archive = root / "Game.rgss3a"

            # Ruby Marshal for an empty array: [].
            _build_rgss3a_single_entry(
                archive,
                name="Data\\MapInfos.rvdata2",
                payload=b"\x04\x08[\x00",
            )

            loader = DataLoader(data_dir, engine="vxace", archive_path=archive)
            self.assertTrue(loader.exists("MapInfos.json"))
            self.assertEqual(loader.load_json("MapInfos.json"), [])


if __name__ == "__main__":
    unittest.main()

