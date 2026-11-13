"""Locating the game, installing / removing the mod and launching it."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import kitfile, modbuild
from .bindings import Settings

STEAM_APP_ID = 1225570
EXE_NAME = "UnravelTwo.exe"
KIT_DIR = "D3D11kits"
KIT_NAME = "Data-01"            # patch archive that holds the Yarny script
BACKUP_DIR = "_SpeedrunHelper/backup"

# SHA1 of the vanilla Steam files this helper was built against
KNOWN_VANILLA = {
    "Data-01.kit": "30532df7eb35157bfdc2ee1331a2b944bf3d9635",
    "Data-01.kit.0": "5c501b9af24b143fc1c3ec8178942321c877e585",
}
VANILLA_YARNY_SHA1 = "46477b1b15de141be1dd325129307ced069d707c"
# leftovers of the hand-made prototype versions
LEGACY_FILES = ("Data.kit.22", "Data-01.kit.1")


class GameError(Exception):
    pass


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- locating

def _steam_root() -> Path | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    for value in ("SteamPath", "InstallPath"):
                        try:
                            p = Path(winreg.QueryValueEx(k, value)[0])
                            if p.exists():
                                return p
                        except OSError:
                            pass
            except OSError:
                pass
    except ImportError:
        pass
    return None


def find_game() -> Path | None:
    """Try to find the Unravel Two folder in all Steam libraries."""
    candidates: list[Path] = []
    root = _steam_root()
    if root:
        candidates.append(root)
        vdf = root / "steamapps" / "libraryfolders.vdf"
        if vdf.exists():
            text = vdf.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'"path"\s+"([^"]+)"', text):
                candidates.append(Path(m.group(1).replace("\\\\", "\\")))
    candidates.append(Path(r"C:\Program Files (x86)\Steam"))
    for lib in candidates:
        game = lib / "steamapps" / "common" / "UnravelTwo"
        if (game / EXE_NAME).exists():
            return game
    return None


def is_game_dir(path: Path) -> bool:
    return (path / EXE_NAME).exists() and (path / KIT_DIR / f"{KIT_NAME}.kit").exists()


def is_game_running() -> bool:
    if sys.platform != "win32":
        return False
    try:
        proc = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH", "/FI", f"IMAGENAME eq {EXE_NAME}"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=0x08000000)  # CREATE_NO_WINDOW
        out = (proc.stdout or b"").decode("mbcs", errors="replace")
        return EXE_NAME.lower() in out.lower()
    except Exception:
        return False


def launch() -> None:
    url = f"steam://rungameid/{STEAM_APP_ID}"
    if sys.platform == "win32":
        os.startfile(url)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", url])


# --------------------------------------------------------------------------- mod handling

class Game:
    def __init__(self, path: Path):
        self.path = Path(path)
        if not is_game_dir(self.path):
            raise GameError(f"'{self.path}' does not look like the Unravel Two folder ({EXE_NAME} not found).")
        self.kits = self.path / KIT_DIR
        self.backup = self.path / BACKUP_DIR

    # -- files
    def _index(self) -> Path:
        return self.kits / f"{KIT_NAME}.kit"

    def _part(self) -> Path:
        return self.kits / f"{KIT_NAME}.kit.0"

    def _backup_index(self) -> Path:
        return self.backup / f"{KIT_NAME}.kit"

    def _backup_part(self) -> Path:
        return self.backup / f"{KIT_NAME}.kit.0"

    # -- state
    def current_mode(self) -> str:
        """'vanilla', 'practice', 'speedrun', 'legacy' or 'unknown'."""
        try:
            index = kitfile.KitIndex.load(self._index())
            parts = {i: self.kits / f"{KIT_NAME}.kit.{i}" for i in range(index.parts)}
            entry = index.entry(modbuild.YARNY_HASH)
            if entry.sha1.hex() == VANILLA_YARNY_SHA1:
                return "vanilla"
            script = kitfile.read_entry(index, parts, modbuild.YARNY_HASH)
        except (OSError, kitfile.KitError):
            return "unknown"
        return modbuild.detect_mode(script)

    def has_backup(self) -> bool:
        return self._backup_index().exists() and self._backup_part().exists()

    def ensure_backup(self) -> None:
        """Keep a copy of the vanilla patch archive. Refuses to back up modified files."""
        mode = self.current_mode()
        if self.has_backup():
            # after a game update Steam restores vanilla files: refresh the backup then
            if mode == "vanilla" and (sha1_file(self._index()) != sha1_file(self._backup_index())
                                      or sha1_file(self._part()) != sha1_file(self._backup_part())):
                shutil.copy2(self._index(), self._backup_index())
                shutil.copy2(self._part(), self._backup_part())
            return
        if mode != "vanilla":
            # the prototype kept its own copies of the originals
            legacy = self.path / "_PracticeMod"
            li, lp = legacy / f"{KIT_NAME}.kit.original", legacy / f"{KIT_NAME}.kit.0.original"
            if li.exists() and lp.exists() and sha1_file(li) == KNOWN_VANILLA["Data-01.kit"] \
                    and sha1_file(lp) == KNOWN_VANILLA["Data-01.kit.0"]:
                self.backup.mkdir(parents=True, exist_ok=True)
                shutil.copy2(li, self._backup_index())
                shutil.copy2(lp, self._backup_part())
                return
            raise GameError(
                "The game files are already modified and no clean backup exists.\n"
                "Please run 'Verify integrity of game files' in Steam once, then try again.")
        self.backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self._index(), self._backup_index())
        shutil.copy2(self._part(), self._backup_part())

    def is_known_version(self) -> bool:
        if not self.has_backup():
            return False
        return (sha1_file(self._backup_index()) == KNOWN_VANILLA["Data-01.kit"]
                and sha1_file(self._backup_part()) == KNOWN_VANILLA["Data-01.kit.0"])

    def _check_not_running(self) -> None:
        if is_game_running():
            raise GameError("Unravel Two is running. Please close the game first.")

    def _cleanup_legacy(self) -> None:
        for name in LEGACY_FILES:
            p = self.kits / name
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)

    def install(self, mode: str, settings: Settings) -> None:
        if mode not in modbuild.MODES:
            raise ValueError(mode)
        self._check_not_running()
        self.ensure_backup()
        index_bytes = self._backup_index().read_bytes()
        part_bytes = self._backup_part().read_bytes()
        index = kitfile.KitIndex(index_bytes)
        if index.parts != 1:
            raise GameError("Unexpected archive layout (game version not supported).")
        vanilla = kitfile.read_entry(index, {0: self._backup_part()}, modbuild.YARNY_HASH)
        script = modbuild.build_script(vanilla, mode, settings)
        new_index, new_part = kitfile.build_patched(index_bytes, part_bytes, {modbuild.YARNY_HASH: script})
        self._cleanup_legacy()
        # write the data part first, then the index that points into it
        self._atomic_write(self._part(), new_part)
        self._atomic_write(self._index(), new_index)

    def uninstall(self) -> None:
        self._check_not_running()
        if not self.has_backup():
            if self.current_mode() == "vanilla":
                self._cleanup_legacy()
                return
            raise GameError("No backup found. Use 'Verify integrity of game files' in Steam to restore the game.")
        self._cleanup_legacy()
        self._atomic_write(self._part(), self._backup_part().read_bytes())
        self._atomic_write(self._index(), self._backup_index().read_bytes())

    def log_path(self) -> Path:
        return self.path / "practice_log.txt"
