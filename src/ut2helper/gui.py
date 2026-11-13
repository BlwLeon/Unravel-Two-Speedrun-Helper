"""Tkinter GUI of the Unravel Two Speedrun Helper."""

from __future__ import annotations

import ctypes
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .bindings import ACTIONS, KEYBOARD_KEYS, PAD_BUTTONS, PAD_DIRECTIONS, Settings
from .game import Game, GameError, find_game, is_game_dir, launch

MODE_TEXT = {
    "vanilla": "Vanilla (no mod)",
    "practice": "Practice mod installed",
    "speedrun": "Speedrun mode installed",
    "legacy": "Old prototype mod installed",
    "unknown": "Unknown / unreadable",
}

# Windows virtual key codes -> key names used by the game
VK_NAMES = {
    0x1B: "ESCAPE", 0x08: "BACKSPACE", 0x09: "TAB", 0x0D: "RETURN", 0x20: "SPACE",
    0x10: "LEFT_SHIFT", 0xA0: "LEFT_SHIFT", 0xA1: "RIGHT_SHIFT",
    0x11: "LEFT_CONTROL", 0xA2: "LEFT_CONTROL", 0xA3: "RIGHT_CONTROL",
    0x12: "LEFT_ALT", 0xA4: "LEFT_ALT", 0xA5: "ALTGR",
    0x14: "CAPS_LOCK", 0x90: "NUM_LOCK", 0x91: "SCROLL_LOCK", 0x13: "PAUSE",
    0x21: "PGUP", 0x22: "PGDN", 0x23: "END", 0x24: "HOME",
    0x25: "LEFT", 0x26: "UP", 0x27: "RIGHT", 0x28: "DOWN",
    0x2D: "INSERT", 0x2E: "DELETE_BTN",
    0x6A: "NUMPAD_MULTIPLY", 0x6B: "NUMPAD_PLUS", 0x6D: "NUMPAD_MINUS",
    0x6E: "NUMPAD_DECIMAL", 0x6F: "NUMPAD_DIVISION",
    0xBC: "COMMA", 0xBE: "DOT", 0xBD: "MINUS", 0xBB: "PLUS", 0xE2: "LESS",
}
for _i in range(10):
    VK_NAMES[0x60 + _i] = f"NUMPAD_{_i}"
    VK_NAMES[0x30 + _i] = f"NUM_{_i}"
for _i in range(12):
    VK_NAMES[0x70 + _i] = f"F{_i + 1}"
for _c in range(ord("A"), ord("Z") + 1):
    VK_NAMES[_c] = chr(_c)


def write_error_log() -> Path:
    """Append the current exception with traceback to error.log next to the settings."""
    import traceback
    log = Settings.path().parent / "error.log"
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"--- {__version__}\n{traceback.format_exc()}\n")
    except OSError:
        pass
    return log


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except Exception:
        return True


def relaunch_as_admin() -> bool:
    if sys.platform != "win32":
        return False
    exe = sys.executable
    params = " ".join(f'"{a}"' for a in sys.argv[1:]) if getattr(sys, "frozen", False) \
        else "-m ut2helper " + " ".join(f'"{a}"' for a in sys.argv[1:])
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)  # type: ignore[attr-defined]
    return rc > 32


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Unravel Two Speedrun Helper {__version__}")
        self.minsize(620, 560)
        self.settings = Settings.load()
        if not self.settings.game_path:
            found = find_game()
            if found:
                self.settings.game_path = str(found)

        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Big.TButton", font=("Segoe UI", 12, "bold"), padding=10)
        style.configure("Status.TLabel", font=("Segoe UI", 10, "bold"))

        self.path_var = tk.StringVar(value=self.settings.game_path)
        self.status_var = tk.StringVar()

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        nb.add(self._build_play(nb), text="Play")
        nb.add(self._build_keys(nb), text="Keyboard")
        nb.add(self._build_pad(nb), text="Controller")
        nb.add(self._build_options(nb), text="Options")
        self.refresh_status()

    # ------------------------------------------------------------------ helpers
    def game(self) -> Game | None:
        path = self.path_var.get().strip()
        if not path:
            messagebox.showwarning("Game folder", "Please select the Unravel Two folder first.")
            return None
        try:
            return Game(Path(path))
        except GameError as e:
            messagebox.showerror("Game folder", str(e))
            return None

    def refresh_status(self):
        path = self.path_var.get().strip()
        if path and is_game_dir(Path(path)):
            g = Game(Path(path))
            mode = g.current_mode()
            extra = "" if not g.has_backup() or g.is_known_version() else "  (unknown game version)"
            self.status_var.set("Current game files: " + MODE_TEXT.get(mode, mode) + extra)
        else:
            self.status_var.set("Game folder not set or invalid")

    def run_action(self, func) -> bool:
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            func()
            return True
        except PermissionError:
            if not is_admin() and messagebox.askyesno(
                    "Administrator rights needed",
                    "Windows does not allow writing to the game folder.\n\nRestart the helper as administrator?"):
                if relaunch_as_admin():
                    self.destroy()
            return False
        except GameError as e:
            messagebox.showerror("Error", str(e))
            return False
        except Exception as e:  # pragma: no cover - last resort
            log = write_error_log()
            messagebox.showerror("Unexpected error", f"{e!r}\n\nDetails were written to:\n{log}")
            return False
        finally:
            self.config(cursor="")
            self.refresh_status()

    # ------------------------------------------------------------------ play tab
    def _build_play(self, parent):
        f = ttk.Frame(parent, padding=12)
        ttk.Label(f, text="Game folder").grid(row=0, column=0, sticky="w")
        e = ttk.Entry(f, textvariable=self.path_var, width=60)
        e.grid(row=1, column=0, columnspan=2, sticky="we", pady=(2, 0))
        ttk.Button(f, text="Browse...", command=self.browse).grid(row=1, column=2, padx=(6, 0))
        ttk.Button(f, text="Auto-detect", command=self.autodetect).grid(row=1, column=3, padx=(6, 0))
        ttk.Label(f, textvariable=self.status_var, style="Status.TLabel").grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(10, 14))

        buttons = (
            ("Play Vanilla", "Original game, mod removed.", self.play_vanilla),
            ("Play Practice Mod", "All practice tools with your key bindings.", self.play_practice),
            ("Play Speedrun Mode", "Only cutscene fast-forward, always on. No other tools.", self.play_speedrun),
        )
        for i, (title, desc, cmd) in enumerate(buttons):
            ttk.Button(f, text=title, style="Big.TButton", command=cmd).grid(
                row=3 + i * 2, column=0, columnspan=4, sticky="we", pady=(6, 0))
            ttk.Label(f, text=desc, foreground="#555").grid(row=4 + i * 2, column=0, columnspan=4, sticky="w")

        bar = ttk.Frame(f)
        bar.grid(row=10, column=0, columnspan=4, sticky="we", pady=(18, 0))
        ttk.Button(bar, text="Restore vanilla files", command=self.restore).pack(side="left")
        ttk.Button(bar, text="Open log", command=self.open_log).pack(side="left", padx=6)
        ttk.Button(bar, text="Open game folder", command=self.open_folder).pack(side="left")
        f.columnconfigure(0, weight=1)
        return f

    def browse(self):
        d = filedialog.askdirectory(title="Select the Unravel Two folder")
        if d:
            self.path_var.set(d)
            self.settings.game_path = d
            self.settings.save()
            self.refresh_status()

    def autodetect(self):
        found = find_game()
        if found:
            self.path_var.set(str(found))
            self.settings.game_path = str(found)
            self.settings.save()
        else:
            messagebox.showinfo("Auto-detect", "Unravel Two was not found in your Steam libraries.")
        self.refresh_status()

    def _play(self, apply):
        g = self.game()
        if not g:
            return
        self.settings.game_path = str(g.path)
        self.settings.save()
        if self.run_action(lambda: apply(g)):
            launch()

    def play_vanilla(self):
        self._play(lambda g: g.uninstall())

    def play_practice(self):
        problems = self.settings.validate()
        if problems:
            messagebox.showerror("Key bindings", "\n".join(problems))
            return
        self._play(lambda g: g.install("practice", self.settings))

    def play_speedrun(self):
        if not messagebox.askokcancel(
                "Speedrun mode",
                "Speedrun mode speeds up cutscenes.\n\nOnly use it for runs if the leaderboard rules "
                "of your category allow it. For normal leaderboard runs use 'Play Vanilla'."):
            return
        self._play(lambda g: g.install("speedrun", self.settings))

    def restore(self):
        g = self.game()
        if g and self.run_action(g.uninstall):
            messagebox.showinfo("Restore", "Vanilla game files restored.")

    def open_log(self):
        g = self.game()
        if g:
            if g.log_path().exists():
                os.startfile(g.log_path())  # type: ignore[attr-defined]
            else:
                messagebox.showinfo("Log", "No log yet. It is created when the modded game runs.")

    def open_folder(self):
        g = self.game()
        if g:
            os.startfile(g.path)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ keyboard tab
    def _build_keys(self, parent):
        f = ttk.Frame(parent, padding=12)
        ttk.Label(f, text="Keyboard bindings for the practice mod. Click 'Set' and press a key, "
                          "or pick one from the list.", wraplength=560).grid(row=0, column=0, columnspan=4, sticky="w")
        self.key_vars: dict[str, tk.StringVar] = {}
        for i, a in enumerate(ACTIONS, start=1):
            ttk.Label(f, text=a.label).grid(row=i, column=0, sticky="w", pady=1)
            var = tk.StringVar(value=self.settings.keys.get(a.id, ""))
            self.key_vars[a.id] = var
            cb = ttk.Combobox(f, textvariable=var, values=("",) + KEYBOARD_KEYS, state="readonly", width=20)
            cb.grid(row=i, column=1, padx=6, pady=1)
            ttk.Button(f, text="Set", width=6, command=lambda v=var: self.capture_key(v)).grid(row=i, column=2)
            ttk.Button(f, text="Clear", width=6, command=lambda v=var: v.set("")).grid(row=i, column=3, padx=(4, 0))
        bar = ttk.Frame(f)
        bar.grid(row=len(ACTIONS) + 2, column=0, columnspan=4, sticky="w", pady=(12, 0))
        ttk.Button(bar, text="Save", command=self.save_settings).pack(side="left")
        ttk.Button(bar, text="Reset to defaults", command=self.reset_keys).pack(side="left", padx=6)
        f.columnconfigure(0, weight=1)
        return f

    def capture_key(self, var: tk.StringVar):
        win = tk.Toplevel(self)
        win.title("Press a key")
        win.geometry("280x90")
        win.transient(self)
        ttk.Label(win, text="Press the key you want to use\n(Esc = cancel)", justify="center").pack(expand=True)
        win.grab_set()
        win.focus_force()

        def on_key(event):
            name = VK_NAMES.get(event.keycode)
            if event.keycode == 0x1B:
                win.destroy()
                return
            if name:
                var.set(name)
                win.destroy()

        win.bind("<KeyPress>", on_key)

    def reset_keys(self):
        for a in ACTIONS:
            self.key_vars[a.id].set(a.default_key)

    # ------------------------------------------------------------------ controller tab
    def _build_pad(self, parent):
        f = ttk.Frame(parent, padding=12)
        ttk.Label(f, wraplength=560, text=(
            "Controller bindings work as combos: hold the modifier button and press a second button "
            "(or push the stick). Buttons are the game's own actions, so they follow your in-game "
            "controller layout. Note: the game still sees the second button press (e.g. Jump).")).grid(
            row=0, column=0, columnspan=2, sticky="w")
        self.pad_enabled_var = tk.BooleanVar(value=self.settings.pad_enabled)
        ttk.Checkbutton(f, text="Enable controller bindings", variable=self.pad_enabled_var).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(8, 4))
        ttk.Label(f, text="Modifier (hold)").grid(row=2, column=0, sticky="w")
        self.pad_mod_var = tk.StringVar(value=self.settings.pad_modifier)
        ttk.Combobox(f, textvariable=self.pad_mod_var, values=PAD_BUTTONS, state="readonly", width=18).grid(
            row=2, column=1, sticky="w", pady=(0, 8))
        self.pad_vars: dict[str, tk.StringVar] = {}
        values = ("",) + PAD_BUTTONS + PAD_DIRECTIONS
        for i, a in enumerate(ACTIONS, start=3):
            if a.id in ("fly_up", "fly_down"):
                continue  # in fly mode up = Jump, down = stick
            ttk.Label(f, text=a.label).grid(row=i, column=0, sticky="w", pady=1)
            var = tk.StringVar(value=self.settings.pad_binds.get(a.id, ""))
            self.pad_vars[a.id] = var
            ttk.Combobox(f, textvariable=var, values=values, state="readonly", width=18).grid(
                row=i, column=1, sticky="w", pady=1)
        bar = ttk.Frame(f)
        bar.grid(row=len(ACTIONS) + 4, column=0, columnspan=2, sticky="w", pady=(12, 0))
        ttk.Button(bar, text="Save", command=self.save_settings).pack(side="left")
        ttk.Button(bar, text="Reset to defaults", command=self.reset_pad).pack(side="left", padx=6)
        f.columnconfigure(0, weight=1)
        return f

    def reset_pad(self):
        for a in ACTIONS:
            if a.id in self.pad_vars:
                self.pad_vars[a.id].set(a.default_pad)

    # ------------------------------------------------------------------ options tab
    def _build_options(self, parent):
        f = ttk.Frame(parent, padding=12)
        self.cs_default_var = tk.BooleanVar(value=self.settings.cutscene_default)
        ttk.Checkbutton(f, text="Practice mod: cutscene fast-forward on at game start",
                        variable=self.cs_default_var).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(f, text="Cutscene speed (characters standing)").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.cs_still_var = tk.StringVar(value=str(self.settings.cs_speed_still))
        ttk.Spinbox(f, from_=2, to=20, increment=1, textvariable=self.cs_still_var, width=6).grid(
            row=1, column=1, sticky="w", pady=(10, 0))
        ttk.Label(f, text="Cutscene speed (characters walking / falling)").grid(row=2, column=0, sticky="w")
        self.cs_moving_var = tk.StringVar(value=str(self.settings.cs_speed_moving))
        ttk.Spinbox(f, from_=1, to=8, increment=1, textvariable=self.cs_moving_var, width=6).grid(
            row=2, column=1, sticky="w")
        ttk.Label(f, foreground="#555", wraplength=560, text=(
            "Higher walking speeds can make the Yarnys fall through the floor.")).grid(
            row=3, column=0, columnspan=2, sticky="w")
        ttk.Button(f, text="Save", command=self.save_settings).grid(row=4, column=0, sticky="w", pady=(14, 0))
        ttk.Separator(f).grid(row=5, column=0, columnspan=2, sticky="we", pady=14)
        ttk.Label(f, wraplength=560, text=(
            f"Unravel Two Speedrun Helper {__version__}\n"
            "Fan-made tool, not affiliated with Coldwood or EA. The mod only changes one game script "
            "and keeps a backup of the original files in '_SpeedrunHelper' inside the game folder.")).grid(
            row=6, column=0, columnspan=2, sticky="w")
        f.columnconfigure(0, weight=1)
        return f

    # ------------------------------------------------------------------ saving
    def save_settings(self):
        s = self.settings
        s.keys = {aid: v.get() for aid, v in self.key_vars.items()}
        s.pad_enabled = self.pad_enabled_var.get()
        s.pad_modifier = self.pad_mod_var.get()
        s.pad_binds = {aid: v.get() for aid, v in self.pad_vars.items() if v.get()}
        s.cutscene_default = self.cs_default_var.get()
        try:
            s.cs_speed_still = max(1.0, min(20.0, float(self.cs_still_var.get())))
            s.cs_speed_moving = max(1.0, min(20.0, float(self.cs_moving_var.get())))
        except ValueError:
            messagebox.showerror("Options", "Cutscene speeds must be numbers.")
            return
        problems = s.validate()
        if problems:
            messagebox.showerror("Bindings", "\n".join(problems))
            return
        s.game_path = self.path_var.get().strip()
        s.save()
        # re-apply if the practice mod is currently installed
        if s.game_path and is_game_dir(Path(s.game_path)):
            g = Game(Path(s.game_path))
            if g.current_mode() == "practice":
                if self.run_action(lambda: g.install("practice", s)):
                    messagebox.showinfo("Saved", "Settings saved and applied to the installed practice mod.")
                return
        messagebox.showinfo("Saved", "Settings saved. They are applied the next time you start the practice mod.")


def run():
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
        except Exception:
            pass
    App().mainloop()
