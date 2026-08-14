# Codex Waybar Usage

A compact Waybar module with a GTK4 hover card for Codex session and weekly usage limits.

It reads limits through the local `codex app-server` interface. It never reads, copies, or prints Codex authentication tokens.

## Requirements

- Codex CLI with ChatGPT login
- Waybar
- Python 3.11+
- PyGObject, GTK4, Cairo, and gtk4-layer-shell

Arch Linux:

```sh
sudo pacman -S waybar python-gobject gtk4 gtk4-layer-shell python-cairo
```

Debian or Ubuntu:

```sh
sudo apt install waybar python3-gi python3-cairo gir1.2-gtk-4.0 gir1.2-gtk4layershell-1.0
```

## Install

```sh
git clone https://github.com/luinbytes/codex-waybar-usage.git
cd codex-waybar-usage
./install.sh
```

Copy the `custom/codex-usage` definition from [`waybar.jsonc`](waybar.jsonc) into your Waybar config, add `custom/codex-usage` to a module list, and include [`waybar.css`](waybar.css) in your stylesheet. Then reload Waybar.

The hover service creates a narrow transparent hitbox over the module on every monitor. Hover it for the usage card, right-click to refresh, or optionally configure a left-click command.

## Configuration

The defaults match a right-aligned module. Set variables in a systemd user-service override when your layout differs:

```ini
[Service]
Environment=CODEX_WAYBAR_HITBOX_RIGHT=88
Environment="CODEX_WAYBAR_LAUNCH=ghostty -e codex"
Environment=CODEX_WAYBAR_THEME=/path/to/colors.toml
Environment=CODEX_BIN=/path/to/codex
```

Run `systemctl --user edit codex-waybar-popup.service`, add the override, then restart the service.

| Variable | Default | Purpose |
| --- | --- | --- |
| `CODEX_WAYBAR_HITBOX_RIGHT` | `88` | Pixels between the right screen edge and hover hitbox |
| `CODEX_WAYBAR_LAUNCH` | unset | Command run by left-click |
| `CODEX_WAYBAR_THEME` | Omarchy theme path | Optional TOML color source; built-in colors are the fallback |
| `CODEX_WAYBAR_LAYER_SHELL` | auto-detected | gtk4-layer-shell library path |
| `CODEX_WAYBAR_SIGNAL` | `13` | Waybar real-time refresh signal; keep it aligned with `waybar.jsonc` |
| `CODEX_WAYBAR_TIMEOUT` | `12` | Codex app-server timeout in seconds |
| `CODEX_BIN` | `codex` | Codex CLI executable |

## Checks

```sh
python3 codex-waybar.py --self-test
python3 codex-waybar.py
```

The second command prints one Waybar JSON object using your current Codex login.

## Privacy and security

The program starts the locally installed Codex app server and requests `account/rateLimits/read`. Credentials remain owned by Codex. Do not add `~/.codex/auth.json`, `.env` files, logs, or personal Waybar configuration to this repository.

## Attribution

The pace calculation and seven-slot burn-down chart are adapted from [CodexBar](https://github.com/steipete/CodexBar), Copyright © 2026 Peter Steinberger, under the MIT License.

## License

MIT
