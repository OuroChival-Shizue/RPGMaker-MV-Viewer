"""Minimal RGSS archive reader for .rgssad/.rgss2a/.rgss3a files."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from .errors import GameDataInvalidError

_RGSS_MAGIC = b"RGSSAD"
_KEY_MASK = 0xFFFFFFFF


def _u32(value: int) -> int:
    return value & _KEY_MASK


def _canonical(path: str) -> str:
    return path.replace("/", "\\").strip().lower()


@dataclass(frozen=True)
class RgssArchiveEntry:
    name: str
    offset: int
    size: int
    data_key: int


class RgssArchive:
    """Reads encrypted entries from RGSS archives."""

    def __init__(self, archive_path: str | Path):
        self.path = Path(archive_path).expanduser().resolve()
        if not self.path.exists() or not self.path.is_file():
            raise GameDataInvalidError(f"RGSS 归档不存在: {self.path}")

        self._entries: dict[str, RgssArchiveEntry] = {}
        self.version = 0
        self._parse_index()

    def has_entry(self, name: str) -> bool:
        return _canonical(name) in self._entries

    def read_entry(self, name: str) -> bytes:
        key = _canonical(name)
        entry = self._entries.get(key)
        if not entry:
            raise KeyError(name)
        return self._read_and_decrypt(entry)

    def _parse_index(self) -> None:
        with self.path.open("rb") as f:
            if f.read(6) != _RGSS_MAGIC:
                raise GameDataInvalidError(f"不是有效 RGSS 归档: {self.path}")
            f.read(1)  # reserved
            ver_raw = f.read(1)
            if not ver_raw:
                raise GameDataInvalidError(f"RGSS 归档头损坏: {self.path}")
            self.version = ver_raw[0]

            if self.version == 3:
                self._parse_v3_index(f)
            elif self.version in (1, 2):
                self._parse_v1_v2_index(f)
            else:
                raise GameDataInvalidError(f"不支持的 RGSS 归档版本: {self.version}")

    def _parse_v3_index(self, f) -> None:
        key_raw = f.read(4)
        if len(key_raw) != 4:
            raise GameDataInvalidError("RGSS3 归档头损坏: 缺少主密钥")
        magic_key = _u32(struct.unpack("<I", key_raw)[0] * 9 + 3)

        while True:
            raw = f.read(16)
            if len(raw) < 16:
                break
            offset, size, data_key, name_len = struct.unpack("<IIII", raw)
            offset ^= magic_key
            if offset == 0:
                break
            size ^= magic_key
            data_key ^= magic_key
            name_len ^= magic_key

            name_enc = f.read(name_len)
            if len(name_enc) != name_len:
                raise GameDataInvalidError("RGSS3 归档索引损坏: 文件名长度不匹配")
            key_bytes = struct.pack("<I", magic_key)
            name = bytes(b ^ key_bytes[i % 4] for i, b in enumerate(name_enc)).decode(
                "utf-8",
                errors="replace",
            )
            entry = RgssArchiveEntry(name=name, offset=offset, size=size, data_key=data_key)
            self._entries[_canonical(name)] = entry

    def _parse_v1_v2_index(self, f) -> None:
        magic_key = 0xDEADCAFE
        while f.tell() < self.path.stat().st_size:
            name_len_raw = f.read(4)
            if not name_len_raw:
                break
            if len(name_len_raw) < 4:
                raise GameDataInvalidError("RGSS 归档索引损坏: 文件名长度字段不完整")
            name_len = struct.unpack("<I", name_len_raw)[0] ^ magic_key
            magic_key = _u32(magic_key * 7 + 3)
            if name_len <= 0:
                break

            name_bytes = bytearray(f.read(name_len))
            if len(name_bytes) != name_len:
                raise GameDataInvalidError("RGSS 归档索引损坏: 文件名内容不完整")
            for i in range(name_len):
                name_bytes[i] ^= magic_key & 0xFF
                magic_key = _u32(magic_key * 7 + 3)
            name = bytes(name_bytes).decode("utf-8", errors="replace")

            size_raw = f.read(4)
            if len(size_raw) < 4:
                raise GameDataInvalidError("RGSS 归档索引损坏: 文件大小字段不完整")
            size = struct.unpack("<I", size_raw)[0] ^ magic_key
            magic_key = _u32(magic_key * 7 + 3)

            offset = f.tell()
            entry = RgssArchiveEntry(name=name, offset=offset, size=size, data_key=magic_key)
            self._entries[_canonical(name)] = entry
            f.seek(size, 1)

    def _read_and_decrypt(self, entry: RgssArchiveEntry) -> bytes:
        with self.path.open("rb") as f:
            f.seek(entry.offset)
            data = bytearray(f.read(entry.size))
        if len(data) != entry.size:
            raise GameDataInvalidError(f"归档数据读取失败: {entry.name}")

        data_key = entry.data_key
        groups = entry.size // 4
        for i in range(groups):
            base = i * 4
            data[base] ^= (data_key >> 0) & 0xFF
            data[base + 1] ^= (data_key >> 8) & 0xFF
            data[base + 2] ^= (data_key >> 16) & 0xFF
            data[base + 3] ^= (data_key >> 24) & 0xFF
            data_key = _u32(data_key * 7 + 3)

        pos = groups * 4
        while pos < entry.size:
            shift = 8 * (pos % 4)
            data[pos] ^= (data_key >> shift) & 0xFF
            pos += 1

        return bytes(data)

