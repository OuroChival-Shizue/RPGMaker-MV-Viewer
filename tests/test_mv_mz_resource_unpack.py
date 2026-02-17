from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from viewer.mv_mz_resource_unpack import (
    load_encryption_key,
    prepare_resources,
    scan_encrypted_resources,
)

_FAKE_HEADER = bytes.fromhex("5250474d560000000003010000000000")


def _encrypt_payload(raw: bytes, key_bytes: bytes) -> bytes:
    buf = bytearray(raw)
    for i in range(min(16, len(buf), len(key_bytes))):
        buf[i] ^= key_bytes[i]
    return bytes(buf)


class MvMzResourceUnpackTest(unittest.TestCase):
    def test_prepare_python_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_root = Path(tmp)
            data_dir = game_root / "www" / "data"
            data_dir.mkdir(parents=True)
            key = "00112233445566778899aabbccddeeff"
            (data_dir / "System.json").write_text(json.dumps({"encryptionKey": key}), encoding="utf-8")

            plain_png = b"\x89PNG\r\n\x1a\n1234567890abcdefTAIL"
            plain_ogg = b"OggS0123456789abcdefTAIL"
            enc_png = _FAKE_HEADER + _encrypt_payload(plain_png, bytes.fromhex(key))
            enc_ogg = _FAKE_HEADER + _encrypt_payload(plain_ogg, bytes.fromhex(key))

            (game_root / "img").mkdir(parents=True)
            (game_root / "audio").mkdir(parents=True)
            (game_root / "img" / "A.rpgmvp").write_bytes(enc_png)
            (game_root / "audio" / "B.ogg_").write_bytes(enc_ogg)

            found = scan_encrypted_resources(game_root)
            self.assertEqual(len(found), 2)

            result = prepare_resources(
                game_root=game_root,
                data_dir=data_dir,
                cache_dir=game_root / "data_cache",
                java_runner=lambda *_: (False, "should not call java"),
            )
            self.assertEqual(result.status, "python_ok")
            self.assertEqual(result.method, "python")
            self.assertEqual(result.processed_files, 2)
            self.assertEqual(result.failed_files, 0)

            out_png = game_root / "data_cache" / "decrypted" / "img" / "A.png"
            out_ogg = game_root / "data_cache" / "decrypted" / "audio" / "B.ogg"
            self.assertTrue(out_png.exists())
            self.assertTrue(out_ogg.exists())
            self.assertEqual(out_png.read_bytes(), plain_png)
            self.assertEqual(out_ogg.read_bytes(), plain_ogg)

    def test_prepare_fallback_failed_without_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_root = Path(tmp)
            data_dir = game_root / "www" / "data"
            data_dir.mkdir(parents=True)
            key_bytes = bytes.fromhex("00112233445566778899aabbccddeeff")
            plain = b"0123456789abcdefHELLO"
            enc = _FAKE_HEADER + _encrypt_payload(plain, key_bytes)
            (game_root / "img").mkdir(parents=True)
            (game_root / "img" / "A.rpgmvp").write_bytes(enc)

            result = prepare_resources(
                game_root=game_root,
                data_dir=data_dir,
                cache_dir=game_root / "data_cache",
                java_runner=lambda *_: (False, "检测到资源封包但无法解包（缺少 Java Decrypter JAR）"),
            )
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.method, "none")
            self.assertIn("缺少 Java Decrypter", result.message)

    def test_load_encryption_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "System.json"
            p.write_text('{"encryptionKey":"00112233445566778899aabbccddeeff"}', encoding="utf-8")
            self.assertEqual(load_encryption_key(p), "00112233445566778899aabbccddeeff")


if __name__ == "__main__":
    unittest.main()

