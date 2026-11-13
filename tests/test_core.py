"""Basic tests that run without the game files."""
import hashlib
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from ut2helper import kitfile, modbuild  # noqa: E402
from ut2helper.bindings import ACTIONS, Settings  # noqa: E402
import lua_balance  # noqa: E402


def make_kit(files: dict[int, bytes]) -> tuple[bytes, bytes]:
    """Build a minimal kit index + part with every file stored LZ4 compressed."""
    part = bytearray()
    entries = []
    for h, data in files.items():
        packed = kitfile.pack_chunks(data)
        entries.append((h, 9, 0, len(part), len(packed), len(data), hashlib.sha1(data).digest()))
        part += packed
    header = bytearray(b"kit!" + b"\0" * 0x1C)
    struct.pack_into("<II", header, 0x18, len(entries), 1)
    body = bytearray()
    for h, t, p, off, cs, us, sha in reversed(entries):  # entries are stored backwards
        e = bytearray(56)
        struct.pack_into("<IIH", e, 0, h, t, p)
        e[10:16] = off.to_bytes(6, "little")
        struct.pack_into("<QQ", e, 16, cs, us)
        e[32:52] = sha
        body += e
    return bytes(header + body + b"!tik"), bytes(part)


FAKE_SCRIPT = (
    "local m_input_hash = 0;\r\n"
    "function Update(self, dt)\r\n"
    "\tUpdateInputConfiguration(self, dt);\r\n\tUpdateWater(self, dt);\r\n"
    "\tPreUpdateOffsetTranslate(self, dt);\r\nend\r\n \r\nfunction PreHierarchyUpdate(self, dt)\r\nend\r\n"
).encode("latin-1")


class KitTests(unittest.TestCase):
    def test_literal_lz4_roundtrip(self):
        data = os.urandom(200_000) + b"A" * 70_000
        out = kitfile.unpack_chunks(kitfile.pack_chunks(data), len(data))
        self.assertEqual(out, data)

    def test_patch_entry(self):
        tmp = Path(tempfile.mkdtemp())
        index, part = make_kit({0x11: b"hello" * 100, modbuild.YARNY_HASH: FAKE_SCRIPT})
        new_script = b"patched" * 1000
        new_index, new_part = kitfile.build_patched(index, part, {modbuild.YARNY_HASH: new_script})
        self.assertTrue(new_part.startswith(part))
        (tmp / "x.kit.0").write_bytes(new_part)
        idx = kitfile.KitIndex(new_index)
        self.assertEqual(kitfile.read_entry(idx, {0: tmp / "x.kit.0"}, modbuild.YARNY_HASH), new_script)
        self.assertEqual(kitfile.read_entry(idx, {0: tmp / "x.kit.0"}, 0x11), b"hello" * 100)


class ModBuildTests(unittest.TestCase):
    def test_build_both_modes(self):
        s = Settings()
        s.pad_enabled = True
        for mode in modbuild.MODES:
            out = modbuild.build_script(FAKE_SCRIPT, mode, s)
            text = out.decode("latin-1")
            self.assertEqual(modbuild.detect_mode(out), mode)
            self.assertEqual(text.count("pcall(PracticeUpdate, self, dt)"), 1)
            self.assertEqual(text.count("pcall(PracticeLateUpdate, self, dt)"), 1)
            self.assertNotIn("__PM_", text)
            lua_balance.check(text)
        self.assertEqual(modbuild.detect_mode(FAKE_SCRIPT), "vanilla")

    def test_speedrun_has_no_binds(self):
        text = modbuild.lua_config("speedrun", Settings())
        self.assertNotIn("NUMPAD", text)

    def test_unknown_version(self):
        with self.assertRaises(modbuild.ModBuildError):
            modbuild.build_script(b"function Foo() end", "practice", Settings())

    def test_default_bindings_valid(self):
        self.assertEqual(Settings().validate(), [])
        self.assertEqual(len({a.id for a in ACTIONS}), len(ACTIONS))


if __name__ == "__main__":
    unittest.main()
