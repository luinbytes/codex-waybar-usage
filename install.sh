#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/codex-waybar-usage"
SYSTEMD_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

for command in python3 codex; do
  command -v "$command" >/dev/null || { echo "Missing dependency: $command" >&2; exit 1; }
done

install -Dm755 "$SOURCE_DIR/codex-waybar.py" "$APP_DIR/codex-waybar.py"
install -Dm644 "$SOURCE_DIR/codex-waybar-popup.service" "$SYSTEMD_DIR/codex-waybar-popup.service"

if [[ "${1:-}" != "--no-enable" ]]; then
  systemctl --user daemon-reload
  systemctl --user enable --now codex-waybar-popup.service
fi

echo "Installed to $APP_DIR"
echo "Add custom/codex-usage from waybar.jsonc to Waybar, include waybar.css, then reload Waybar."
