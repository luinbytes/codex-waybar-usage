#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/grok-waybar-usage"
COMPAT_DIR="$HOME/.local/share/codex-waybar-usage"
SYSTEMD_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNIT_NAME="grok-waybar-popup.service"
ALIAS_NAME="codex-waybar-popup.service"

command -v python3 >/dev/null || { echo "Missing dependency: python3" >&2; exit 1; }

install -Dm755 "$SOURCE_DIR/grok-waybar.py" "$APP_DIR/grok-waybar.py"
install -Dm755 "$SOURCE_DIR/codex-waybar.py" "$APP_DIR/codex-waybar.py"
mkdir -p "$COMPAT_DIR"
ln -sfn "$APP_DIR/grok-waybar.py" "$COMPAT_DIR/grok-waybar.py"
ln -sfn "$APP_DIR/codex-waybar.py" "$COMPAT_DIR/codex-waybar.py"

install -Dm644 "$SOURCE_DIR/$UNIT_NAME" "$SYSTEMD_DIR/$UNIT_NAME"

alias_path="$SYSTEMD_DIR/$ALIAS_NAME"
if [[ -e "$alias_path" && ! -L "$alias_path" ]]; then
  # Drop the previous standalone unit so this name can alias the Grok unit.
  systemctl --user disable --now "$ALIAS_NAME" >/dev/null 2>&1 || true
  rm -f "$alias_path"
fi
ln -sfn "$UNIT_NAME" "$alias_path"

if [[ "${1:-}" != "--no-enable" ]]; then
  systemctl --user daemon-reload
  systemctl --user enable --now "$UNIT_NAME"
fi

echo "Installed to $APP_DIR"
echo "Compatibility exec path: $COMPAT_DIR/codex-waybar.py"
echo "Add custom/grok-usage from waybar.jsonc to Waybar. custom/codex-usage still works."
echo "Include waybar.css, then reload Waybar."
