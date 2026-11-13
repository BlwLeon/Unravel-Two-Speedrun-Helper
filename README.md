# Unravel Two Speedrun Helper

A practice tool for **Unravel Two** speedrunners (Steam version, PC).
One small program that switches your game between **Vanilla**, a **Practice Mod** with
practice tools, and a **Speedrun Mode** – and starts the game for you.

> Fan-made tool. Not affiliated with Coldwood Interactive or Electronic Arts.
> No game files are included or distributed – the helper modifies your own installation
> and keeps a backup of the original files.

---

## Features

| Practice Mod | Default key |
|---|---|
| Fly mode (noclip) – move with your normal controls, **Jump** = up | `Num 0` |
| Fly up / down (hold) | `Num 8` / `Num 5` |
| Fly speed down / up (0.5× – 8×) | `Num 7` / `Num 9` |
| Reload last checkpoint | `Num 1` |
| Save / load position (both Yarnys) | `Num 2` / `Num 3` |
| Previous / next checkpoint of the current level | `Num 4` / `Num 6` |
| Checkpoint jump with automatic checkpoint restart on/off | `Num ,` (decimal) |
| Cutscene fast-forward on/off | `Num *` |
| Game speed up / down (0.25× – 4×) | `Num +` / `Num -` |
| Diagnostic log on/off | `Num /` |

* All keys can be **re-bound** in the helper (no numpad needed).
* **Controller support:** hold a modifier button (default: *Hint*) and press a second
  button or push the stick, e.g. *Hint + Jump* = reload checkpoint.
* **Speedrun Mode:** all practice tools are disabled, only the cutscene fast-forward is
  active and cannot be turned off.
* **Vanilla:** restores the original files with one click.

### How the tools behave

* **Checkpoint jumping** teleports both Yarnys to the checkpoint and then restarts the
  checkpoint, so the level section is loaded properly. Jumping **backwards** restarts the
  level first (the game never re-activates an earlier checkpoint) and jumps to the target
  automatically afterwards.
* **Save / load position** undocks a carried Yarny first, then teleports both. You have to
  dock again after loading.
* **Cutscene fast-forward** detects cutscenes (no Yarny accepts input, input configuration
  disabled by the cutscene, scripted animations) and runs the game at 20× while the
  Yarnys stand still and 5× while they walk or fall – higher speeds make them fall
  through the floor. Speeds can be changed in *Options*.
* The camera may stay behind when flying out of a camera zone – that is how the game's
  rail cameras work, not a bug of the mod.

---

## Installation

1. Download `UT2SpeedrunHelper.exe` from the [Releases](../../releases) page.
2. Start it. The game folder is detected automatically (Steam libraries); otherwise use
   *Browse…* and select the `UnravelTwo` folder
   (e.g. `C:\Program Files (x86)\Steam\steamapps\common\UnravelTwo`).
3. Click **Play Practice Mod**, **Play Speedrun Mode** or **Play Vanilla**.
   The helper changes the game files and starts the game through Steam.

If Windows refuses to write to the game folder, the helper offers to restart itself as
administrator.

### Uninstall

Click **Restore vanilla files** (or *Play Vanilla*). Alternatively use
*Steam → Unravel Two → Properties → Installed Files → Verify integrity of game files*.
The backup of the original files lives in `UnravelTwo\_SpeedrunHelper\backup` and can be
deleted afterwards.

### Command line

```
UT2SpeedrunHelper.exe install practice   [--game PATH]
UT2SpeedrunHelper.exe install speedrun   [--game PATH]
UT2SpeedrunHelper.exe uninstall          [--game PATH]
UT2SpeedrunHelper.exe status             [--game PATH]
```

---

## Key bindings

* **Keyboard tab:** click *Set* and press a key, or pick one from the list.
  Duplicate keys are rejected.
* **Controller tab:** enable controller bindings, pick the modifier button and a second
  button / stick direction per tool. Buttons are the game's own actions (Jump, Grab,
  Lasso, Tie, …), so they follow your controller layout in the game options.
  The game still receives the second button (e.g. holding *Hint* and pressing *Jump*
  also makes the Yarny jump).

Changes are applied immediately if the Practice Mod is installed, otherwise the next
time you start it.

---

## Speedrun rules

The Practice Mod is for practice only. **Speedrun Mode changes the game** (faster
cutscenes) – only use it for runs if the leaderboard of your category explicitly allows
it. For normal leaderboard runs use **Play Vanilla**.

---

## How it works

Unravel Two's gameplay logic is written in Lua and stored in the game's `.kit`
archives (an index file plus LZ4-compressed data parts). The Yarny player script lives in
the patch archive `D3D11kits/Data-01.kit`.

The helper:

1. backs up `Data-01.kit` and `Data-01.kit.0`,
2. extracts the original Yarny script,
3. inserts the mod code (`src/ut2helper/lua/practice_mod.lua`, with your settings as a
   generated config table) and two hook calls into `Update()`,
4. appends the modified script to `Data-01.kit.0` and points the index entry at it
   (SHA1 updated).

The game executable is not touched. The archive format is documented in
[`src/ut2helper/kitfile.py`](src/ut2helper/kitfile.py).

After a game update the helper refreshes its backup from the new vanilla files. If the
Yarny script changed so much that the hook points cannot be found, it refuses to
install instead of breaking the game.

---

## Building from source

Requirements: Windows, Python 3.10+.

```
python run_helper.py            # run the GUI from source
python -m unittest discover -s tests
build.bat                       # builds dist\UT2SpeedrunHelper.exe with PyInstaller
```

Every push builds the exe via GitHub Actions; pushing a tag `v*` creates a release.

### Project layout

```
src/ut2helper/
  gui.py          Tkinter GUI
  cli.py          command line + entry point
  game.py         game detection, backup, install/uninstall, launch via Steam
  kitfile.py      .kit archive reader/writer (LZ4)
  modbuild.py     builds the modded Yarny script
  bindings.py     actions, default keys, settings (%APPDATA%\UnravelTwoSpeedrunHelper)
  lua/practice_mod.lua   the in-game mod
tests/            unit tests (no game files needed)
tools/            small dev helpers
```

---

## Troubleshooting

* **Nothing happens when pressing keys** – make sure the Practice Mod is installed
  (status line in the helper) and the game was restarted afterwards.
* **"The game files are already modified"** – run *Verify integrity of game files* in
  Steam once, then use the helper again.
* **Log file:** `UnravelTwo\practice_log.txt` (button *Open log*). Turn on the diagnostic
  log (`Num /`) for detailed state output when reporting bugs.

---

## License

MIT – see [LICENSE](LICENSE).
