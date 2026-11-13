"""Command line interface (also used by the GUI-less installer).

    UT2SpeedrunHelper.exe                     -> opens the GUI
    UT2SpeedrunHelper.exe install [practice|speedrun] [--game PATH]
    UT2SpeedrunHelper.exe uninstall [--game PATH]
    UT2SpeedrunHelper.exe status [--game PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .bindings import Settings
from .game import Game, GameError, find_game


def _report(text: str, error: bool = False) -> None:
    """Print, or show a message box when running as windowed exe (no console)."""
    if sys.stdout is not None and sys.stderr is not None:
        print(text, file=sys.stderr if error else sys.stdout)
        return
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, "Unravel Two Speedrun Helper", 0x10 if error else 0x40)
    except Exception:
        pass


def _game(args, settings: Settings) -> Game:
    path = args.game or settings.game_path or find_game()
    if not path:
        raise GameError("Unravel Two was not found. Pass the folder with --game.")
    return Game(Path(path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="UT2SpeedrunHelper", description="Unravel Two Speedrun Helper " + __version__)
    sub = parser.add_subparsers(dest="cmd")
    p_inst = sub.add_parser("install", help="install the mod")
    p_inst.add_argument("mode", nargs="?", default="practice", choices=["practice", "speedrun"])
    p_inst.add_argument("--game")
    p_un = sub.add_parser("uninstall", help="restore the vanilla game files")
    p_un.add_argument("--game")
    p_st = sub.add_parser("status", help="show the current state")
    p_st.add_argument("--game")
    args = parser.parse_args(argv)

    if args.cmd is None:
        from .gui import run
        run()
        return 0

    settings = Settings.load()
    try:
        game = _game(args, settings)
        if args.cmd == "install":
            game.install(args.mode, settings)
            _report(f"Installed ({args.mode}) in {game.path}")
        elif args.cmd == "uninstall":
            game.uninstall()
            _report("Vanilla files restored.")
        elif args.cmd == "status":
            _report(f"Game folder : {game.path}\n"
                    f"Mode        : {game.current_mode()}\n"
                    f"Backup      : {'yes' if game.has_backup() else 'no'}")
    except GameError as e:
        _report(f"Error: {e}", error=True)
        return 1
    return 0
