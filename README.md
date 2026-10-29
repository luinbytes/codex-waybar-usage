# Grok Waybar Usage

A small Waybar module that shows your remaining Grok weekly usage on Cursor. Hover over it to open a GTK4 card with session usage, weekly pace, reset time, and a seven-day burn-down chart.

The module reads the signed-in Cursor billing period. It does not print the Cursor access token. The GitHub repository name is still `codex-waybar-usage`.

## What you get

- A compact `[USG 79%]` Waybar label
- A hover card on each monitor
- Right-click refresh and an optional left-click command
- Built-in colors, with optional Omarchy theme support

## Requirements

- Cursor, signed in
- Waybar
- Python 3.11 or newer
- PyGObject, GTK4, Cairo, and gtk4-layer-shell

Install the desktop dependencies first.

Arch Linux:

```sh
sudo pacman -S waybar python-gobject gtk4 gtk4-layer-shell python-cairo
```

Debian or Ubuntu:

```sh
sudo apt install waybar python3-gi python3-cairo gir1.2-gtk-4.0 gir1.2-gtk4layershell-1.0
```

The live module does not call the Codex CLI. A legacy helper still shells out to `codex app-server` for old Codex rate-limit payloads. That path keeps the `codex` command, `CODEX_BIN`, and the Codex `account/rateLimits/read` method.

## Install

1. Clone the repository and run the installer:

   ```sh
   git clone https://github.com/luinbytes/codex-waybar-usage.git
   cd codex-waybar-usage
   ./install.sh
   ```

   The installer copies the program to `~/.local/share/grok-waybar-usage/` and starts `grok-waybar-popup.service`. It also leaves `~/.local/share/codex-waybar-usage/codex-waybar.py` in place, and aliases the previous systemd unit name.

2. Copy the `custom/grok-usage` module from [`waybar.jsonc`](waybar.jsonc) into your Waybar config. If you already have `custom/codex-usage`, keep that instead of adding a second module.

3. Add `custom/grok-usage` to `modules-right`, `modules-center`, or `modules-left`. The default hover position expects `modules-right`.

4. Append the rules from [`waybar.css`](waybar.css) to your Waybar stylesheet. Those rules style both `#custom-grok-usage` and `#custom-codex-usage`. If your stylesheet does not define `@accent`, replace `@accent` with a color such as `#7aa2f7`.

5. Reload Waybar, then hover over the usage label:

   ```sh
   pkill -SIGUSR2 waybar
   ```

## Migration

Project identity is Grok. Repository name stays `codex-waybar-usage`.

| Old | New | Still works? |
| --- | --- | --- |
| `codex-waybar.py` | `grok-waybar.py` | Yes. The old filename is a shim that runs the new script. |
| `~/.local/share/codex-waybar-usage/codex-waybar.py` | `~/.local/share/grok-waybar-usage/grok-waybar.py` | Yes, after you reinstall. The installer keeps the old path as a symlink. |
| `custom/codex-usage` | `custom/grok-usage` | Yes. Leave the old module id in Waybar, or switch the `exec` path when you want. Do not enable both. |
| `#custom-codex-usage` and its `.active`, `.inactive`, and `.warning` selectors | `#custom-grok-usage` | Yes. `waybar.css` lists both ids. JSON output also includes the classes `codex-usage` and `grok-usage`. |
| `codex-waybar-popup.service` | `grok-waybar-popup.service` | Yes. The new unit lists the old name as an alias, and the installer links that name. |
| `CODEX_WAYBAR_HITBOX_RIGHT`, `CODEX_WAYBAR_LAUNCH`, `CODEX_WAYBAR_THEME`, `CODEX_WAYBAR_LAYER_SHELL`, `CODEX_WAYBAR_SIGNAL`, `CODEX_WAYBAR_PRELOADED`, `CODEX_WAYBAR_TIMEOUT` | `GROK_WAYBAR_HITBOX_RIGHT`, `GROK_WAYBAR_LAUNCH`, `GROK_WAYBAR_THEME`, `GROK_WAYBAR_LAYER_SHELL`, `GROK_WAYBAR_SIGNAL`, `GROK_WAYBAR_PRELOADED`, `GROK_USAGE_TIMEOUT` | Yes. The `GROK_` value wins. If only the old name is set, it is still read and a deprecation note is written to stderr. |

Change these when you want the new names:

- Point Waybar `exec` at `~/.local/share/grok-waybar-usage/grok-waybar.py`.
- Use module id `custom/grok-usage`.
- Move systemd overrides to `grok-waybar-popup.service`.
- Rename widget settings from `CODEX_WAYBAR_*` to the `GROK_` names above.

Leave these as Codex. They talk to the Codex product, not this widget's name:

- `CODEX_BIN` and the `codex` executable
- `codex app-server` and `account/rateLimits/read`
- The `codex` entry in `rateLimitsByLimitId`
- `~/.codex` paths, including `~/.codex/auth.json`, which this program does not read

## Set it up with an agent

Paste this prompt into a coding agent running on your desktop:

```text
Set up Grok Waybar Usage on this machine.

Repository: https://github.com/luinbytes/codex-waybar-usage

Goal:
- Add the Grok usage label to my existing Waybar.
- Make the GTK hover card line up with the label.
- Preserve my current Waybar layout and styling.
- If custom/codex-usage is already configured, keep that single module. Do not add a second copy.

Safety rules:
- Inspect my current Waybar config, stylesheet, running processes, and systemd user services before changing anything.
- Do not replace my full Waybar config or stylesheet. Merge only the required module and CSS rules.
- Preserve unrelated local changes.
- Do not read, print, copy, or commit authentication files, tokens, environment files, or logs.
- Use dynamic home and config paths. Do not hard-code my username, monitor names, screen size, terminal, or theme path.

Tasks:
1. Check that Waybar, a signed-in Cursor install, Python 3.11+, PyGObject, GTK4, Cairo, and gtk4-layer-shell are available. Install only missing desktop packages using the correct package manager for this system.
2. Clone or update the repository in a sensible user-owned source directory.
3. Run ./install.sh from the repository.
4. Find the active Waybar config. If custom/codex-usage is already there, leave it. Otherwise merge the custom/grok-usage object from waybar.jsonc into it.
5. Add that one module id to the correct module list without reordering my other modules.
6. Merge the rules from waybar.css into the active stylesheet. Adapt only undefined color variables so they match my existing theme.
7. If the label is not right-aligned, create a systemd user-service override for GROK_WAYBAR_HITBOX_RIGHT so the transparent hover hitbox lines up with the module. CODEX_WAYBAR_HITBOX_RIGHT still works when the new name is unset.
8. Reload Waybar and restart grok-waybar-popup.service. Do not restart my desktop session.

Verification:
- Run python3 grok-waybar.py --self-test from the repository.
- Run python3 codex-waybar.py --self-test and confirm it passes too.
- Run the installed script once and confirm that it prints valid Waybar JSON.
- Confirm grok-waybar-popup.service is active. codex-waybar-popup.service is an alias of that unit.
- Confirm the usage label appears in the existing bar.
- Test the hover card on every connected monitor and adjust only GROK_WAYBAR_HITBOX_RIGHT if alignment is wrong.
- Check the final diff for secrets, personal paths, and accidental changes outside this setup.

Report:
- List every file changed.
- State the installed path and service status.
- Record the final GROK_WAYBAR_HITBOX_RIGHT value if you changed it.
- Separate automated checks from anything I still need to verify visually.
```

## Configuration

Use a systemd user-service override for local settings:

```sh
systemctl --user edit grok-waybar-popup.service
```

Example override:

```ini
[Service]
Environment=GROK_WAYBAR_HITBOX_RIGHT=88
Environment=GROK_WAYBAR_THEME=/path/to/colors.toml
Environment=GROK_USAGE_TIMEOUT=12
```

Restart the service after saving the override:

```sh
systemctl --user restart grok-waybar-popup.service
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `GROK_WAYBAR_HITBOX_RIGHT` | `88` | Pixels between the right screen edge and hover hitbox. `CODEX_WAYBAR_HITBOX_RIGHT` is still accepted. |
| `GROK_WAYBAR_LAUNCH` | unset | Command run by left-click. `CODEX_WAYBAR_LAUNCH` is still accepted. |
| `GROK_WAYBAR_THEME` | auto | Uses Omarchy colors when present, otherwise built-in colors. `CODEX_WAYBAR_THEME` is still accepted. |
| `GROK_WAYBAR_LAYER_SHELL` | auto-detected | gtk4-layer-shell library path. `CODEX_WAYBAR_LAYER_SHELL` is still accepted. |
| `GROK_WAYBAR_SIGNAL` | `13` | Waybar refresh signal; keep it aligned with `waybar.jsonc`. `CODEX_WAYBAR_SIGNAL` is still accepted. |
| `GROK_USAGE_TIMEOUT` | `12` | Cursor usage request timeout in seconds. `CODEX_WAYBAR_TIMEOUT` is still accepted. |
| `CODEX_BIN` | `codex` | Codex CLI executable for the legacy app-server helper. The live widget does not call it. |

`CODEX_WAYBAR_PRELOADED` is an internal reload flag. `GROK_WAYBAR_PRELOADED` replaces it, and the old flag is still honored.

## Check the installation

From the cloned repository:

```sh
python3 grok-waybar.py --self-test
python3 grok-waybar.py
python3 codex-waybar.py
python3 -m unittest discover -s tests -v
systemctl --user status grok-waybar-popup.service
```

The middle commands print one Waybar JSON object from the signed-in Cursor account. Without that login, print the same shape from the fixture:

```sh
python3 grok-waybar.py --fixture tests/fixtures/cursor_usage.json
python3 codex-waybar.py --fixture tests/fixtures/cursor_usage.json
```

## Privacy and security

The program reads the Cursor access token from the local Cursor state database and sends it only to Cursor's current-period usage endpoint. It does not print that token. It does not read `~/.codex/auth.json`. Do not add that file, `.env` files, logs, or personal Waybar configuration to this repository.

## Attribution

The pace calculation and seven-slot burn-down chart are adapted from [CodexBar](https://github.com/steipete/CodexBar), Copyright © 2026 Peter Steinberger, under the MIT License.

## License

MIT
