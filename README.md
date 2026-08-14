# Codex Waybar Usage

A small Waybar module that shows your remaining Codex weekly usage. Hover over it to open a GTK4 card with session usage, weekly pace, reset time, and a seven-day burn-down chart.

The module gets usage data from the local `codex app-server`. It does not read or print Codex authentication tokens.

## What you get

- A compact `[USG 79%]` Waybar label
- A hover card on each monitor
- Right-click refresh and an optional left-click command
- Built-in colors, with optional Omarchy theme support

## Requirements

- Codex CLI, signed in with ChatGPT
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

## Install

1. Clone the repository and run the installer:

   ```sh
   git clone https://github.com/luinbytes/codex-waybar-usage.git
   cd codex-waybar-usage
   ./install.sh
   ```

   The installer copies the program to `~/.local/share/codex-waybar-usage/` and starts `codex-waybar-popup.service`.

2. Copy the `custom/codex-usage` module from [`waybar.jsonc`](waybar.jsonc) into your Waybar config.

3. Add `custom/codex-usage` to `modules-right`, `modules-center`, or `modules-left`. The default hover position expects `modules-right`.

4. Append the rules from [`waybar.css`](waybar.css) to your Waybar stylesheet. If your stylesheet does not define `@accent`, replace `@accent` with a color such as `#7aa2f7`.

5. Reload Waybar, then hover over the usage label:

   ```sh
   pkill -SIGUSR2 waybar
   ```

## Set it up with an agent

Paste this prompt into Codex or another coding agent running on your desktop:

```text
Set up Codex Waybar Usage on this machine.

Repository: https://github.com/luinbytes/codex-waybar-usage

Goal:
- Add the Codex usage label to my existing Waybar.
- Make the GTK hover card line up with the label.
- Preserve my current Waybar layout and styling.

Safety rules:
- Inspect my current Waybar config, stylesheet, running processes, and systemd user services before changing anything.
- Do not replace my full Waybar config or stylesheet. Merge only the required module and CSS rules.
- Preserve unrelated local changes.
- Do not read, print, copy, or commit authentication files, tokens, environment files, or logs.
- Use dynamic home and config paths. Do not hard-code my username, monitor names, screen size, terminal, or theme path.

Tasks:
1. Check that Waybar, the Codex CLI, Python 3.11+, PyGObject, GTK4, Cairo, and gtk4-layer-shell are available. Install only missing desktop packages using the correct package manager for this system.
2. Clone or update the repository in a sensible user-owned source directory.
3. Run ./install.sh from the repository.
4. Find the active Waybar config and merge the custom/codex-usage object from waybar.jsonc into it.
5. Add custom/codex-usage to the correct module list without reordering my other modules.
6. Merge the rules from waybar.css into the active stylesheet. Adapt only undefined color variables so they match my existing theme.
7. If the label is not right-aligned, create a systemd user-service override for CODEX_WAYBAR_HITBOX_RIGHT so the transparent hover hitbox lines up with the module.
8. Reload Waybar and restart codex-waybar-popup.service. Do not restart my desktop session.

Verification:
- Run python3 codex-waybar.py --self-test from the repository.
- Run the installed script once and confirm that it prints valid Waybar JSON.
- Confirm codex-waybar-popup.service is active.
- Confirm the usage label appears in the existing bar.
- Test the hover card on every connected monitor and adjust only CODEX_WAYBAR_HITBOX_RIGHT if alignment is wrong.
- Check the final diff for secrets, personal paths, and accidental changes outside this setup.

Report:
- List every file changed.
- State the installed path and service status.
- Record the final CODEX_WAYBAR_HITBOX_RIGHT value if you changed it.
- Separate automated checks from anything I still need to verify visually.
```

## Configuration

Use a systemd user-service override for local settings:

```sh
systemctl --user edit codex-waybar-popup.service
```

Example override:

```ini
[Service]
Environment=CODEX_WAYBAR_HITBOX_RIGHT=88
Environment=CODEX_WAYBAR_THEME=/path/to/colors.toml
Environment=CODEX_BIN=/path/to/codex
```

Restart the service after saving the override:

```sh
systemctl --user restart codex-waybar-popup.service
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `CODEX_WAYBAR_HITBOX_RIGHT` | `88` | Pixels between the right screen edge and hover hitbox |
| `CODEX_WAYBAR_LAUNCH` | unset | Command run by left-click |
| `CODEX_WAYBAR_THEME` | auto | Uses Omarchy colors when present, otherwise built-in colors |
| `CODEX_WAYBAR_LAYER_SHELL` | auto-detected | gtk4-layer-shell library path |
| `CODEX_WAYBAR_SIGNAL` | `13` | Waybar refresh signal; keep it aligned with `waybar.jsonc` |
| `CODEX_WAYBAR_TIMEOUT` | `12` | Codex app-server timeout in seconds |
| `CODEX_BIN` | `codex` | Codex CLI executable |

## Check the installation

From the cloned repository:

```sh
python3 codex-waybar.py --self-test
python3 codex-waybar.py
systemctl --user status codex-waybar-popup.service
```

The second command should print one Waybar JSON object using your current Codex login.

## Privacy and security

The program starts the locally installed Codex app server and requests `account/rateLimits/read`. Codex keeps ownership of the credentials. Do not add `~/.codex/auth.json`, `.env` files, logs, or personal Waybar configuration to this repository.

## Attribution

The pace calculation and seven-slot burn-down chart are adapted from [CodexBar](https://github.com/steipete/CodexBar), Copyright © 2026 Peter Steinberger, under the MIT License.

## License

MIT
