"""Builds the modded Yarny script from the vanilla one plus the mod template."""

from __future__ import annotations

import re
from importlib import resources

from . import __version__
from .bindings import ACTIONS, Settings

# Name hash of the Yarny player behaviour script inside Data-01.kit
YARNY_HASH = 0x6630CDD6

# Anchors in the vanilla script (CRLF line endings)
ANCHOR_UPDATE = "function Update(self, dt)\r\n"
ANCHOR_EARLY = "\tUpdateInputConfiguration(self, dt);\r\n\tUpdateWater(self, dt);"
ANCHOR_LATE = "\tPreUpdateOffsetTranslate(self, dt);\r\nend\r\n \r\nfunction PreHierarchyUpdate"

MARKER_RE = re.compile(r"UT2SH-MARKER mode=(\w+) version=([\w.\-]+)")
LEGACY_MARKER = "SPEEDRUN PRACTICE MOD"

MODES = ("practice", "speedrun")

# The game seems to refuse scripts above ~538 KB (538 488 bytes works, 539 483
# gives a black screen). Stay well below that.
MAX_SCRIPT_SIZE = 535_000


class ModBuildError(Exception):
    pass


def _lua_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def lua_config(mode: str, settings: Settings) -> str:
    if mode not in MODES:
        raise ValueError(mode)
    lines = ["{", f"\tmode = {_lua_str(mode)},"]
    lines.append("\tbinds = {")
    if mode == "practice":
        for action in ACTIONS:
            names = []
            key = settings.keys.get(action.id)
            if key:
                names.append(key)
            pad = settings.pad_binds.get(action.id)
            if pad and settings.pad_enabled:
                names.append("PAD:" + pad)
            if names:
                lines.append(f"\t\t{action.id} = {{ {', '.join(_lua_str(n) for n in names)} }},")
    lines.append("\t},")
    lines.append("\tpad = { enabled = %s, modifier = %s }," % (
        "true" if (settings.pad_enabled and mode == "practice") else "false",
        _lua_str(settings.pad_modifier)))
    lines.append("\tcutscene_default = %s," % ("true" if settings.cutscene_default else "false"))
    lines.append("\tcs_speed_still = %s," % float(settings.cs_speed_still))
    lines.append("\tcs_speed_moving = %s," % float(settings.cs_speed_moving))
    lines.append("}")
    return "\n".join(lines)


def template() -> str:
    text = resources.files("ut2helper").joinpath("lua/practice_mod.lua").read_text(encoding="utf-8")
    # The game resolves CWHASH("...") while loading the script; any other argument
    # makes the whole script fail to load (black screen).
    if re.search(r'CWHASH\((?!")', text):
        raise ModBuildError("CWHASH() must only be used with string literals in the mod template.")
    return text


def _strip_comment_lines(text: str, dedent: bool) -> str:
    """Remove full-line comments (and blank lines / indentation if ``dedent``).

    Safe for these scripts: they contain no multi-line strings, and lines that open
    or close a block comment (``--[[`` / ``]]``) are kept.
    """
    out = []
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("--") and "[[" not in s and "]]" not in s and "UT2SH-MARKER" not in s:
            continue
        if dedent:
            if not s:
                continue
            line = s
        out.append(line)
    return "\n".join(out)


def build_script(vanilla: bytes, mode: str, settings: Settings) -> bytes:
    src = vanilla.decode("latin-1")
    for name, anchor in (("Update", ANCHOR_UPDATE), ("early hook", ANCHOR_EARLY), ("late hook", ANCHOR_LATE)):
        if src.count(anchor) != 1:
            raise ModBuildError(
                f"Unsupported game version: anchor '{name}' not found in the Yarny script. "
                "The game was probably updated.")
    mod = template()
    mod = mod.replace("__PM_CONFIG__", lua_config(mode, settings))
    mod = mod.replace("__PM_MODE__", mode).replace("__PM_VERSION__", __version__)
    mod = _strip_comment_lines(mod.replace("\r\n", "\n"), dedent=True)
    mod = mod.rstrip("\n").replace("\n", "\r\n") + "\r\n"
    src = src.replace(ANCHOR_UPDATE, mod + ANCHOR_UPDATE)
    src = src.replace(ANCHOR_EARLY,
                      "\tUpdateInputConfiguration(self, dt);\r\n\tpcall(PracticeUpdate, self, dt);\r\n\tUpdateWater(self, dt);")
    src = src.replace(ANCHOR_LATE, "\tpcall(PracticeLateUpdate, self, dt);\r\n" + ANCHOR_LATE)
    data = src.encode("latin-1")
    if len(data) > MAX_SCRIPT_SIZE:
        raise ModBuildError(f"Modded script too large ({len(data)} bytes, limit {MAX_SCRIPT_SIZE}).")
    return data


def detect_mode(script: bytes) -> str:
    """Return 'vanilla', 'practice', 'speedrun' or 'legacy' for a Yarny script."""
    text = script.decode("latin-1", errors="replace")
    m = MARKER_RE.search(text)
    if m:
        return m.group(1)
    if LEGACY_MARKER in text:
        return "legacy"
    return "vanilla"
