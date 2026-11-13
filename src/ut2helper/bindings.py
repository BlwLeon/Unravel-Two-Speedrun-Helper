"""Actions, default key bindings and the persisted user settings."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Action:
    id: str
    label: str
    default_key: str
    default_pad: str = ""


# Order = order in the settings window
ACTIONS: tuple[Action, ...] = (
    Action("fly_toggle", "Fly mode on/off", "NUMPAD_0", "Down"),
    Action("fly_up", "Fly up (hold)", "NUMPAD_8"),
    Action("fly_down", "Fly down (hold)", "NUMPAD_5"),
    Action("fly_slower", "Fly speed down", "NUMPAD_7"),
    Action("fly_faster", "Fly speed up", "NUMPAD_9"),
    Action("checkpoint_reload", "Reload checkpoint", "NUMPAD_1", "Jump"),
    Action("position_save", "Save position", "NUMPAD_2", "Grab"),
    Action("position_load", "Load position", "NUMPAD_3", "Shoot"),
    Action("checkpoint_prev", "Previous checkpoint", "NUMPAD_4", "Left"),
    Action("checkpoint_next", "Next checkpoint", "NUMPAD_6", "Right"),
    Action("checkpoint_restart_toggle", "Checkpoint jump: auto restart on/off", "NUMPAD_DECIMAL"),
    Action("cutscene_toggle", "Cutscene fast-forward on/off", "NUMPAD_MULTIPLY", "Up"),
    Action("speed_up", "Game speed up", "NUMPAD_PLUS"),
    Action("speed_down", "Game speed down", "NUMPAD_MINUS"),
    Action("diag_toggle", "Diagnostic log on/off", "NUMPAD_DIVISION"),
)

# Key names as the game reports them (without the "CWKEY_" prefix)
KEYBOARD_KEYS: tuple[str, ...] = (
    "ESCAPE", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "SCROLL_LOCK", "PAUSE", "SECTION",
    "NUM_1", "NUM_2", "NUM_3", "NUM_4", "NUM_5", "NUM_6", "NUM_7", "NUM_8", "NUM_9", "NUM_0",
    "PLUS", "ACENT", "BACKSPACE", "INSERT", "HOME", "PGUP", "NUM_LOCK",
    "NUMPAD_DIVISION", "NUMPAD_MULTIPLY", "NUMPAD_MINUS", "TAB",
    "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "AA", "DIAERESIS", "RETURN",
    "DELETE_BTN", "END", "PGDN", "NUMPAD_7", "NUMPAD_8", "NUMPAD_9", "NUMPAD_PLUS", "CAPS_LOCK",
    "A", "S", "D", "F", "G", "H", "J", "K", "L", "OE", "AE", "APOSTROPHE",
    "NUMPAD_4", "NUMPAD_5", "NUMPAD_6", "LEFT_SHIFT", "LESS",
    "Z", "X", "C", "V", "B", "N", "M", "COMMA", "DOT", "MINUS", "RIGHT_SHIFT", "UP",
    "NUMPAD_1", "NUMPAD_2", "NUMPAD_3", "NUMPAD_RETURN",
    "LEFT_CONTROL", "LEFT_WINDOWS", "LEFT_ALT", "SPACE", "ALTGR", "RIGHT_CONTROL",
    "LEFT", "DOWN", "RIGHT", "NUMPAD_0", "NUMPAD_DECIMAL",
)

# In-game actions that can be read from the controller (they follow the player's
# own controller layout in the game options). Plus stick directions.
PAD_BUTTONS: tuple[str, ...] = (
    "Jump", "Grab", "Shoot", "Tie", "RemoteUntie", "DockOrSwitch", "Hint",
    "EmoteWaiting", "EmoteAttention", "EmotePositive", "EmoteNegative", "SlowMo",
)
PAD_DIRECTIONS: tuple[str, ...] = ("Up", "Down", "Left", "Right")

DEFAULT_PAD_MODIFIER = "Hint"


@dataclass
class Settings:
    game_path: str = ""
    keys: dict[str, str] = field(default_factory=lambda: {a.id: a.default_key for a in ACTIONS})
    pad_enabled: bool = False
    pad_modifier: str = DEFAULT_PAD_MODIFIER
    pad_binds: dict[str, str] = field(default_factory=lambda: {a.id: a.default_pad for a in ACTIONS if a.default_pad})
    cutscene_default: bool = False
    cs_speed_still: float = 20.0
    cs_speed_moving: float = 5.0

    # ------------------------------------------------------------------ persistence
    @staticmethod
    def path() -> Path:
        base = os.environ.get("APPDATA") or str(Path.home() / ".config")
        return Path(base) / "UnravelTwoSpeedrunHelper" / "settings.json"

    @classmethod
    def load(cls) -> "Settings":
        p = cls.path()
        s = cls()
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                for k, v in data.items():
                    if hasattr(s, k):
                        setattr(s, k, v)
            except (OSError, ValueError):
                pass
        # fill actions added in newer versions
        for a in ACTIONS:
            s.keys.setdefault(a.id, a.default_key)
        return s

    def save(self) -> None:
        p = self.path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def validate(self) -> list[str]:
        """Return a list of problems (duplicate bindings etc.)."""
        problems = []
        seen: dict[str, str] = {}
        for a in ACTIONS:
            k = self.keys.get(a.id)
            if not k:
                continue
            if k not in KEYBOARD_KEYS:
                problems.append(f"Unknown key '{k}' for '{a.label}'")
            if k in seen:
                problems.append(f"Key {k} is used for both '{seen[k]}' and '{a.label}'")
            seen[k] = a.label
        if self.pad_enabled:
            seen.clear()
            for a in ACTIONS:
                b = self.pad_binds.get(a.id)
                if not b:
                    continue
                if b == self.pad_modifier:
                    problems.append(f"'{a.label}' uses the modifier button itself")
                if b in seen:
                    problems.append(f"Controller {b} is used for both '{seen[b]}' and '{a.label}'")
                seen[b] = a.label
        return problems
