"""8-bit styled Tkinter GUI of the Unravel Two Speedrun Helper."""

from __future__ import annotations

import ctypes
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from . import __version__
from . import pixelfont as pf
from .bindings import ACTIONS, KEYBOARD_KEYS, PAD_BUTTONS, PAD_DIRECTIONS, Settings
from .game import Game, GameError, find_game, is_game_dir, launch

# ----------------------------------------------------------------------------- look

P = {
    "bg": "#efebe0", "paper": "#fbf8f0", "white": "#ffffff", "ink": "#16244a",
    "blue": "#2350b0", "blue_d": "#152f6e", "blue_l": "#4f7fe0", "blue_ll": "#8fb0f5",
    "green": "#6db04f", "green_d": "#3b7a2a", "green_l": "#a6dc84",
    "yellow": "#f5c842", "yellow_d": "#b9851a", "yellow_l": "#ffe48a",
    "gray": "#cfcabd", "gray_d": "#8b8679", "gray_l": "#ece8dd",
    "red": "#e33a45", "red_d": "#9e1d27", "red_l": "#ff8a92",
    "shadow": "#d3cdbd", "muted": "#7d786c",
}

KINDS = {  # face, dark edge, light edge, text, text shadow
    "green": (P["green"], P["green_d"], P["green_l"], P["white"], P["green_d"]),
    "yellow": (P["yellow"], P["yellow_d"], P["yellow_l"], P["white"], P["yellow_d"]),
    "blue": (P["blue_l"], P["blue"], P["blue_ll"], P["white"], P["blue"]),
    "red": (P["red"], P["red_d"], P["red_l"], P["white"], P["red_d"]),
    "gray": (P["gray"], P["gray_d"], P["gray_l"], P["ink"], None),
    "tab": (P["gray_l"], P["gray"], P["white"], P["ink"], None),
    "tab_on": (P["yellow"], P["yellow_d"], P["yellow_l"], P["ink"], None),
}

U = 1          # UI scale (2 on high-DPI screens), set in run()
MONO = ("Consolas", -13, "bold")


def px(n: float) -> int:
    return int(round(n * U))


def lighten(color: str, amount: float = 0.15) -> str:
    c = color.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (int(v + (255 - v) * amount) for v in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def draw_text(c: tk.Canvas, x: int, y: int, text: str, scale: int, fill: str,
              anchor: str = "nw", shadow: str | None = None, tag: str = "") -> None:
    s = scale
    w, h = pf.text_width(text, s), pf.text_height(s)
    if anchor == "center":
        x, y = x - w // 2, y - h // 2
    elif anchor == "w":
        y = y - h // 2
    pixels = list(pf.pixels(text))
    if shadow:
        o = max(1, s // 2)
        for gx, gy in pixels:
            c.create_rectangle(x + gx * s + o, y + gy * s + o, x + gx * s + s + o, y + gy * s + s + o,
                               fill=shadow, width=0, tags=tag)
    for gx, gy in pixels:
        c.create_rectangle(x + gx * s, y + gy * s, x + gx * s + s, y + gy * s + s, fill=fill, width=0, tags=tag)


def draw_box(c: tk.Canvas, x0, y0, x1, y1, face, dark, light, u, border=None, tag="") -> None:
    """Pixel box with stepped corners, light top/left edge and dark bottom/right edge."""
    border = border or P["ink"]
    c.create_rectangle(x0 + u, y0, x1 - u, y1, fill=border, width=0, tags=tag)
    c.create_rectangle(x0, y0 + u, x1, y1 - u, fill=border, width=0, tags=tag)
    c.create_rectangle(x0 + u, y0 + u, x1 - u, y1 - u, fill=face, width=0, tags=tag)
    c.create_rectangle(x0 + u, y0 + u, x1 - u, y0 + 2 * u, fill=light, width=0, tags=tag)
    c.create_rectangle(x0 + u, y0 + u, x0 + 2 * u, y1 - u, fill=light, width=0, tags=tag)
    c.create_rectangle(x0 + u, y1 - 2 * u, x1 - u, y1 - u, fill=dark, width=0, tags=tag)
    c.create_rectangle(x1 - 2 * u, y0 + u, x1 - u, y1 - u, fill=dark, width=0, tags=tag)


# ----------------------------------------------------------------------------- widgets

class PixelButton(tk.Canvas):
    def __init__(self, parent, text: str, command=None, kind: str = "gray", scale: int = 2,
                 width: int | None = None, height: int | None = None, bg: str | None = None):
        self.text, self.kind, self.scale, self.command = text, kind, px(scale), command
        tw = pf.text_width(text, self.scale)
        self.bw = width or tw + px(28)
        self.bh = height or pf.text_height(self.scale) + px(20)
        self.sh = px(5)  # drop shadow
        super().__init__(parent, width=self.bw + self.sh, height=self.bh + self.sh,
                         bg=bg or parent["bg"], highlightthickness=0, bd=0, cursor="hand2")
        self.hover = self.pressed = False
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False, pressed=False))
        self.bind("<ButtonPress-1>", lambda e: self._set(pressed=True))
        self.bind("<ButtonRelease-1>", self._release)
        self.draw()

    def set_kind(self, kind: str) -> None:
        self.kind = kind
        self.draw()

    def _set(self, **kw) -> None:
        for k, v in kw.items():
            setattr(self, k, v)
        self.draw()

    def _release(self, _e) -> None:
        was = self.pressed
        self._set(pressed=False)
        if was and self.hover and self.command:
            self.after(10, self.command)

    def draw(self) -> None:
        self.delete("all")
        face, dark, light, fg, tshadow = KINDS[self.kind]
        if self.hover:
            face, light = lighten(face, 0.18), lighten(light, 0.2)
        o = self.sh if self.pressed else 0
        if not self.pressed:
            self.create_rectangle(self.sh, self.sh, self.bw + self.sh, self.bh + self.sh, fill=P["shadow"], width=0)
        u = max(px(2), self.scale - px(1))
        draw_box(self, o, o, self.bw + o, self.bh + o, face, dark, light, u)
        draw_text(self, o + self.bw // 2, o + self.bh // 2, self.text, self.scale, fg, "center", tshadow)


class LoadingBar(tk.Canvas):
    """Decorative status bar on top of the window ("READY", "LOADING...")."""

    SEGMENTS = 18

    def __init__(self, parent):
        super().__init__(parent, width=px(320), height=px(60), bg=P["bg"], highlightthickness=0)
        self.text, self.filled, self._job = "READY", self.SEGMENTS, None
        self.draw()

    def draw(self) -> None:
        self.delete("all")
        w = px(320)
        draw_text(self, w // 2, px(12), self.text, px(3), P["blue"], "center")
        y0 = px(28)
        self.create_rectangle(0, y0, w, y0 + px(22), fill=P["blue"], width=0)
        self.create_rectangle(px(4), y0 + px(4), w - px(4), y0 + px(18), fill=P["white"], width=0)
        seg = (w - px(16)) / self.SEGMENTS
        for i in range(self.filled):
            x = px(8) + i * seg
            self.create_rectangle(x, y0 + px(7), x + seg - px(4), y0 + px(15), fill=P["blue"], width=0)

    def animate(self, text: str) -> None:
        self.text, self.filled = text, 0
        self._step()

    def _step(self) -> None:
        self.filled = (self.filled + 1) % (self.SEGMENTS + 1)
        self.draw()
        self._job = self.after(45, self._step)

    def done(self, text: str = "READY") -> None:
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        self.text, self.filled = text, self.SEGMENTS
        self.draw()


class PixelDialog(tk.Toplevel):
    """Modal dialog in the same style (replaces tkinter.messagebox)."""

    def __init__(self, parent, title: str, text: str, buttons=(("OK", True),), kind: str = "info"):
        super().__init__(parent)
        self.result = None
        self.title(title.title())
        self.configure(bg=P["blue"])
        self.resizable(False, False)
        self.transient(parent)
        head = tk.Canvas(self, height=px(34), bg=P["blue"], highlightthickness=0, width=px(420))
        head.pack(fill="x")
        draw_text(head, px(12), px(17), title.upper(), px(2), P["white"], "w")
        color = {"error": P["red"], "warn": P["yellow"]}.get(kind, P["blue_l"])
        head.create_rectangle(px(388), px(7), px(408), px(27), fill=color, width=0)
        body = tk.Frame(self, bg=P["white"], padx=px(16), pady=px(14))
        body.pack(fill="both", expand=True, padx=px(4), pady=(0, px(4)))
        tk.Label(body, text=text, bg=P["white"], fg=P["ink"], font=MONO, justify="left",
                 wraplength=px(390)).pack(anchor="w")
        bar = tk.Frame(body, bg=P["white"])
        bar.pack(anchor="e", pady=(px(14), 0))
        for label, value in buttons:
            PixelButton(bar, label, command=lambda v=value: self.close(v),
                        kind="green" if value is True else "gray").pack(side="left", padx=(px(8), 0))
        self.bind("<Escape>", lambda e: self.close(None))
        self.bind("<Return>", lambda e: self.close(buttons[0][1]))
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.grab_set()
        self.focus_force()

    def close(self, value) -> None:
        self.result = value
        self.grab_release()
        self.destroy()

    @classmethod
    def show(cls, parent, title, text, buttons=(("OK", True),), kind="info"):
        d = cls(parent, title, text, buttons, kind)
        parent.wait_window(d)
        return d.result


# ----------------------------------------------------------------------------- helpers

MODE_TEXT = {
    "vanilla": "Vanilla - no mod installed",
    "practice": "Practice mod installed",
    "speedrun": "Speedrun mode installed",
    "legacy": "Old prototype mod installed",
    "unknown": "Unknown / unreadable game files",
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


# ----------------------------------------------------------------------------- app

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("UT2 Speedrun Helper")
        self.configure(bg=P["bg"])
        self.resizable(False, False)
        self.settings = Settings.load()
        if not self.settings.game_path:
            found = find_game()
            if found:
                self.settings.game_path = str(found)

        self._style()
        self.path_var = tk.StringVar(value=self.settings.game_path)
        self.status_var = tk.StringVar()

        self.bar = LoadingBar(self)
        self.bar.pack(pady=(px(14), px(10)))

        window = tk.Frame(self, bg=P["blue"], padx=px(6), pady=0)
        window.pack(padx=px(22), pady=(0, px(22)))
        head = tk.Canvas(window, width=px(700), height=px(50), bg=P["blue"], highlightthickness=0)
        head.pack(fill="x")
        draw_text(head, px(14), px(25), "UT2 SPEEDRUN HELPER.EXE", px(3), P["white"], "w")
        draw_text(head, px(560), px(28), "V" + __version__, px(2), P["blue_ll"], "w")
        head.create_rectangle(px(658), px(10), px(688), px(40), fill=P["red"], width=0)
        draw_text(head, px(673), px(25), "♥", px(2), P["white"], "center")

        content = tk.Frame(window, bg=P["paper"], padx=px(16), pady=px(14))
        content.pack(fill="both", expand=True, pady=(0, px(6)))

        tabs = tk.Frame(content, bg=P["paper"])
        tabs.pack(anchor="w", pady=(0, px(12)))
        self.pages: dict[str, tk.Frame] = {}
        self.tab_buttons: dict[str, PixelButton] = {}
        holder = tk.Frame(content, bg=P["paper"], width=px(668), height=px(600))
        holder.pack(fill="both", expand=True)
        holder.pack_propagate(False)
        for name, builder in (("PLAY", self._build_play), ("KEYBOARD", self._build_keys),
                              ("CONTROLLER", self._build_pad), ("OPTIONS", self._build_options)):
            b = PixelButton(tabs, name, command=lambda n=name: self.show_page(n), kind="tab")
            b.pack(side="left", padx=(0, px(8)))
            self.tab_buttons[name] = b
            page = tk.Frame(holder, bg=P["paper"])
            builder(page)
            self.pages[name] = page
        self.show_page("PLAY")
        self.refresh_status()

    # ------------------------------------------------------------------ styling
    def _style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Pixel.TCombobox", fieldbackground=P["white"], background=P["gray"],
                        foreground=P["ink"], arrowcolor=P["ink"], bordercolor=P["blue"],
                        lightcolor=P["white"], darkcolor=P["gray"], padding=px(3), arrowsize=px(14))
        style.map("Pixel.TCombobox", fieldbackground=[("readonly", P["white"])],
                  selectbackground=[("readonly", P["white"])], selectforeground=[("readonly", P["ink"])])
        self.option_add("*TCombobox*Listbox.font", MONO)
        self.option_add("*TCombobox*Listbox.background", P["white"])
        self.option_add("*TCombobox*Listbox.selectBackground", P["blue"])

    def combobox(self, parent, var, values, width=18):
        cb = ttk.Combobox(parent, textvariable=var, values=values, state="readonly", width=width,
                          style="Pixel.TCombobox", font=MONO)
        return cb

    def label(self, parent, text, muted=False, **kw):
        return tk.Label(parent, text=text, bg=P["paper"], fg=P["muted"] if muted else P["ink"],
                        font=MONO, justify="left", **kw)

    def heading(self, parent, text, color=None):
        c = tk.Canvas(parent, height=px(18), width=pf.text_width(text, px(2)) + px(4),
                      bg=P["paper"], highlightthickness=0)
        draw_text(c, 0, px(2), text, px(2), color or P["blue"])
        return c

    def check(self, parent, text, var):
        return tk.Checkbutton(parent, text=text, variable=var, bg=P["paper"], fg=P["ink"],
                              activebackground=P["paper"], selectcolor=P["white"], font=MONO,
                              highlightthickness=0, bd=0, cursor="hand2")

    def show_page(self, name: str) -> None:
        for n, page in self.pages.items():
            page.pack_forget()
            self.tab_buttons[n].set_kind("tab_on" if n == name else "tab")
        self.pages[name].pack(fill="both", expand=True)

    # ------------------------------------------------------------------ dialogs
    def info(self, title, text):
        PixelDialog.show(self, title, text)

    def error(self, title, text):
        PixelDialog.show(self, title, text, kind="error")

    def ask(self, title, text, yes="YES", no="NO") -> bool:
        return PixelDialog.show(self, title, text, ((yes, True), (no, False)), kind="warn") is True

    # ------------------------------------------------------------------ helpers
    def game(self) -> Game | None:
        path = self.path_var.get().strip()
        if not path:
            self.error("Game folder", "Please select the Unravel Two folder first.")
            return None
        try:
            return Game(Path(path))
        except GameError as e:
            self.error("Game folder", str(e))
            return None

    def refresh_status(self) -> None:
        path = self.path_var.get().strip()
        if path and is_game_dir(Path(path)):
            g = Game(Path(path))
            mode = g.current_mode()
            extra = ""
            if g.has_backup() and not g.is_known_version():
                extra = "   (unknown game version)"
            self.status_var.set(MODE_TEXT.get(mode, mode) + extra)
        else:
            self.status_var.set("Game folder not set or invalid")

    def run_action(self, func, busy_text="LOADING...") -> bool:
        self.bar.animate(busy_text)
        self.config(cursor="watch")
        self.update()
        ok = False
        try:
            func()
            ok = True
        except PermissionError:
            self.bar.done("ERROR")
            if not is_admin() and self.ask(
                    "Administrator rights needed",
                    "Windows does not allow writing to the game folder.\n\nRestart the helper as administrator?"):
                if relaunch_as_admin():
                    self.destroy()
                    return False
        except GameError as e:
            self.bar.done("ERROR")
            self.error("Error", str(e))
        except Exception as e:  # pragma: no cover - last resort
            self.bar.done("ERROR")
            log = write_error_log()
            self.error("Unexpected error", f"{e!r}\n\nDetails were written to:\n{log}")
        finally:
            self.config(cursor="")
        if ok:
            self.bar.done("READY")
        self.refresh_status()
        return ok

    # ------------------------------------------------------------------ play page
    def _build_play(self, f: tk.Frame) -> None:
        box = tk.Frame(f, bg=P["blue"], padx=px(4), pady=0)
        box.pack(fill="x")
        title = tk.Canvas(box, height=px(24), bg=P["blue"], highlightthickness=0)
        title.pack(fill="x")
        draw_text(title, px(6), px(12), "STATUS", px(2), P["white"], "w")
        tk.Label(box, textvariable=self.status_var, bg=P["white"], fg=P["ink"], font=MONO,
                 anchor="w", padx=px(10), pady=px(10)).pack(fill="x", pady=(0, px(4)))

        self.heading(f, "GAME FOLDER").pack(anchor="w", pady=(px(16), px(4)))
        row = tk.Frame(f, bg=P["paper"])
        row.pack(fill="x")
        entry = tk.Entry(row, textvariable=self.path_var, font=MONO, relief="flat", bg=P["white"],
                         fg=P["ink"], highlightthickness=px(3), highlightbackground=P["blue"],
                         highlightcolor=P["blue"], insertbackground=P["ink"])
        entry.pack(side="left", fill="x", expand=True, ipady=px(4))
        entry.bind("<FocusOut>", lambda e: self.refresh_status())
        PixelButton(row, "AUTO", self.autodetect).pack(side="right", padx=(px(8), 0))
        PixelButton(row, "BROWSE", self.browse).pack(side="right", padx=(px(10), 0))

        big = (("▶ PRACTICE", "green", "All practice tools with your key bindings.", self.play_practice),
               ("▶ SPEEDRUN", "yellow", "Only cutscene fast-forward - always on, nothing else.", self.play_speedrun),
               ("▶ VANILLA", "blue", "Original game, mod removed.", self.play_vanilla))
        for i, (text, kind, desc, cmd) in enumerate(big):
            PixelButton(f, text, cmd, kind=kind, scale=5, width=px(650), height=px(66)).pack(
                anchor="w", pady=(px(18) if i == 0 else px(10), 0))
            self.label(f, desc, muted=True).pack(anchor="w", padx=px(4))

        bar = tk.Frame(f, bg=P["paper"])
        bar.pack(anchor="w", pady=(px(18), 0))
        PixelButton(bar, "RESTORE FILES", self.restore).pack(side="left", padx=(0, px(10)))
        PixelButton(bar, "OPEN LOG", self.open_log).pack(side="left", padx=(0, px(10)))
        PixelButton(bar, "GAME FOLDER", self.open_folder).pack(side="left")

    def browse(self) -> None:
        d = filedialog.askdirectory(title="Select the Unravel Two folder")
        if d:
            self.path_var.set(d)
            self.settings.game_path = d
            self.settings.save()
            self.refresh_status()

    def autodetect(self) -> None:
        found = find_game()
        if found:
            self.path_var.set(str(found))
            self.settings.game_path = str(found)
            self.settings.save()
        else:
            self.info("Auto-detect", "Unravel Two was not found in your Steam libraries.")
        self.refresh_status()

    def _play(self, apply) -> None:
        g = self.game()
        if not g:
            return
        self.settings.game_path = str(g.path)
        self.settings.save()
        if self.run_action(lambda: apply(g)):
            self.bar.done("STARTING GAME")
            launch()
            self.after(4000, lambda: self.bar.done("READY"))

    def play_vanilla(self) -> None:
        self._play(lambda g: g.uninstall())

    def play_practice(self) -> None:
        problems = self.settings.validate()
        if problems:
            self.error("Key bindings", "\n".join(problems))
            return
        self._play(lambda g: g.install("practice", self.settings))

    def play_speedrun(self) -> None:
        if not self.ask("Speedrun mode",
                        "Speedrun mode speeds up cutscenes.\n\nOnly use it for runs if the leaderboard "
                        "rules of your category allow it. For normal leaderboard runs use VANILLA.",
                        yes="START", no="CANCEL"):
            return
        self._play(lambda g: g.install("speedrun", self.settings))

    def restore(self) -> None:
        g = self.game()
        if g and self.run_action(g.uninstall):
            self.info("Restore", "Vanilla game files restored.")

    def open_log(self) -> None:
        g = self.game()
        if g:
            if g.log_path().exists():
                os.startfile(g.log_path())  # type: ignore[attr-defined]
            else:
                self.info("Log", "No log yet. It is created when the modded game runs.")

    def open_folder(self) -> None:
        g = self.game()
        if g:
            os.startfile(g.path)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ keyboard page
    def _build_keys(self, f: tk.Frame) -> None:
        self.heading(f, "KEYBOARD").pack(anchor="w")
        self.label(f, "Click SET and press a key, or pick one from the list (empty = unbound).", muted=True).pack(
            anchor="w", pady=(px(2), px(8)))
        grid = tk.Frame(f, bg=P["paper"])
        grid.pack(fill="x")
        self.key_vars: dict[str, tk.StringVar] = {}
        for i, a in enumerate(ACTIONS):
            self.label(grid, a.label).grid(row=i, column=0, sticky="w", pady=px(1))
            var = tk.StringVar(value=self.settings.keys.get(a.id, ""))
            self.key_vars[a.id] = var
            self.combobox(grid, var, ("",) + KEYBOARD_KEYS).grid(row=i, column=1, padx=px(8))
            PixelButton(grid, "SET", lambda v=var: self.capture_key(v), height=px(26)).grid(row=i, column=2)
        grid.columnconfigure(0, weight=1)
        bar = tk.Frame(f, bg=P["paper"])
        bar.pack(anchor="w", pady=(px(14), 0))
        PixelButton(bar, "SAVE", self.save_settings, kind="green").pack(side="left", padx=(0, px(10)))
        PixelButton(bar, "DEFAULTS", self.reset_keys).pack(side="left")

    def capture_key(self, var: tk.StringVar) -> None:
        d = tk.Toplevel(self)
        d.title("Press a key")
        d.configure(bg=P["blue"])
        d.resizable(False, False)
        d.transient(self)
        c = tk.Canvas(d, width=px(320), height=px(110), bg=P["white"], highlightthickness=0)
        c.pack(padx=px(4), pady=px(4))
        draw_text(c, px(160), px(40), "PRESS A KEY", px(3), P["blue"], "center")
        draw_text(c, px(160), px(78), "ESC = CANCEL", px(2), P["muted"], "center")
        d.update_idletasks()
        d.geometry(f"+{self.winfo_rootx() + px(200)}+{self.winfo_rooty() + px(250)}")
        d.grab_set()
        d.focus_force()

        def on_key(event):
            if event.keycode == 0x1B:
                d.destroy()
                return
            name = VK_NAMES.get(event.keycode)
            if name:
                var.set(name)
                d.destroy()

        d.bind("<KeyPress>", on_key)

    def reset_keys(self) -> None:
        for a in ACTIONS:
            self.key_vars[a.id].set(a.default_key)

    # ------------------------------------------------------------------ controller page
    def _build_pad(self, f: tk.Frame) -> None:
        self.heading(f, "CONTROLLER").pack(anchor="w")
        self.label(f, "Hold the modifier button and press a second button (or push the stick).\n"
                      "Buttons are the game's own actions and follow your in-game layout.\n"
                      "The game still sees the second button (e.g. Jump).", muted=True).pack(
            anchor="w", pady=(px(2), px(6)))
        self.pad_enabled_var = tk.BooleanVar(value=self.settings.pad_enabled)
        self.check(f, "Enable controller bindings", self.pad_enabled_var).pack(anchor="w")
        top = tk.Frame(f, bg=P["paper"])
        top.pack(anchor="w", pady=(px(6), px(8)))
        self.label(top, "Modifier (hold)").pack(side="left")
        self.pad_mod_var = tk.StringVar(value=self.settings.pad_modifier)
        self.combobox(top, self.pad_mod_var, PAD_BUTTONS).pack(side="left", padx=px(10))
        grid = tk.Frame(f, bg=P["paper"])
        grid.pack(fill="x")
        self.pad_vars: dict[str, tk.StringVar] = {}
        values = ("",) + PAD_BUTTONS + PAD_DIRECTIONS
        row = 0
        for a in ACTIONS:
            if a.id in ("fly_up", "fly_down"):
                continue  # in fly mode: up = Jump, down = stick
            self.label(grid, a.label).grid(row=row, column=0, sticky="w", pady=px(1))
            var = tk.StringVar(value=self.settings.pad_binds.get(a.id, ""))
            self.pad_vars[a.id] = var
            self.combobox(grid, var, values).grid(row=row, column=1, padx=px(8))
            row += 1
        grid.columnconfigure(0, weight=1)
        bar = tk.Frame(f, bg=P["paper"])
        bar.pack(anchor="w", pady=(px(14), 0))
        PixelButton(bar, "SAVE", self.save_settings, kind="green").pack(side="left", padx=(0, px(10)))
        PixelButton(bar, "DEFAULTS", self.reset_pad).pack(side="left")

    def reset_pad(self) -> None:
        for a in ACTIONS:
            if a.id in self.pad_vars:
                self.pad_vars[a.id].set(a.default_pad)

    # ------------------------------------------------------------------ options page
    def _build_options(self, f: tk.Frame) -> None:
        self.heading(f, "CUTSCENES").pack(anchor="w")
        self.cs_default_var = tk.BooleanVar(value=self.settings.cutscene_default)
        self.check(f, "Practice mod: fast-forward on at game start", self.cs_default_var).pack(
            anchor="w", pady=(px(6), px(8)))
        grid = tk.Frame(f, bg=P["paper"])
        grid.pack(anchor="w")
        self.cs_still_var = tk.StringVar(value=str(self.settings.cs_speed_still))
        self.cs_moving_var = tk.StringVar(value=str(self.settings.cs_speed_moving))
        for r, (text, var, lo, hi) in enumerate((
                ("Speed while the Yarnys stand still", self.cs_still_var, 2, 20),
                ("Speed while they walk / fall", self.cs_moving_var, 1, 8))):
            self.label(grid, text).grid(row=r, column=0, sticky="w", pady=px(3))
            tk.Spinbox(grid, from_=lo, to=hi, increment=1, textvariable=var, width=6, font=MONO,
                       relief="flat", bg=P["white"], fg=P["ink"], buttonbackground=P["gray"],
                       highlightthickness=px(2), highlightbackground=P["blue"],
                       highlightcolor=P["blue"]).grid(row=r, column=1, padx=px(12))
        self.label(f, "Higher walking speeds can make the Yarnys fall through the floor.",
                   muted=True).pack(anchor="w", pady=(px(4), 0))
        PixelButton(f, "SAVE", self.save_settings, kind="green").pack(anchor="w", pady=(px(14), 0))

        self.heading(f, "ABOUT").pack(anchor="w", pady=(px(28), px(4)))
        self.label(f, f"Unravel Two Speedrun Helper {__version__}\n"
                      "Fan-made tool, not affiliated with Coldwood or EA.\n"
                      "The mod only changes one game script and keeps a backup of\n"
                      "the original files in '_SpeedrunHelper' inside the game folder.",
                   muted=True).pack(anchor="w")

    # ------------------------------------------------------------------ saving
    def save_settings(self) -> None:
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
            self.error("Options", "Cutscene speeds must be numbers.")
            return
        problems = s.validate()
        if problems:
            self.error("Bindings", "\n".join(problems))
            return
        s.game_path = self.path_var.get().strip()
        s.save()
        if s.game_path and is_game_dir(Path(s.game_path)):
            g = Game(Path(s.game_path))
            if g.current_mode() == "practice":
                if self.run_action(lambda: g.install("practice", s), "SAVING..."):
                    self.info("Saved", "Settings saved and applied to the installed practice mod.")
                return
        self.info("Saved", "Settings saved. They are applied the next time you start the practice mod.")


def run() -> None:
    global U, MONO
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
        except Exception:
            pass
    probe = tk.Tk()
    probe.withdraw()
    try:
        U = 2 if probe.winfo_fpixels("1i") >= 144 else 1
    except tk.TclError:
        U = 1
    probe.destroy()
    family = "Consolas" if sys.platform == "win32" else "Courier"
    MONO = (family, -13 * U, "bold")
    App().mainloop()
