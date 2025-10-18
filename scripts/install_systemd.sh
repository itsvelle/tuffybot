#!/usr/bin/env bash
# Installs the tuffybot systemd unit from the repo's systemd/ folder.
# Usage: ./scripts/install_systemd.sh [--system|--user] [--enable] [--start]
# Defaults to --system if run as root, otherwise --user.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
UNIT_SRC="$REPO_ROOT/systemd/tuffybot.service"

show_help() {
  cat <<EOF
Usage: $0 [--system|--user] [--enable] [--start]

Options:
  --system   Install to /etc/systemd/system (requires root).
  --user     Install to user systemd (~/.config/systemd/user).
  --enable   Enable the unit after installation.
  --start    Start the unit after installation.
  --help     Show this help.

The script will substitute %i in the unit with the username.
EOF
}

MODE=""
ENABLE=false
START=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --system) MODE=system; shift ;;
    --user) MODE=user; shift ;;
    --enable) ENABLE=true; shift ;;
    --start) START=true; shift ;;
    --help) show_help; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; show_help; exit 2 ;;
  esac
done

CURRENT_USER="$(id -un)"

if [[ -z "$MODE" ]]; then
  if [[ $(id -u) -eq 0 ]]; then
    MODE=system
  else
    MODE=user
  fi
fi

if [[ ! -f "$UNIT_SRC" ]]; then
  echo "Unit source not found: $UNIT_SRC" >&2
  exit 1
fi

render_unit() {
  # Replace %i with username in a safe way
  sed "s|%i|${CURRENT_USER}|g" "$UNIT_SRC"
}

if [[ "$MODE" == "system" ]]; then
  if [[ $(id -u) -ne 0 ]]; then
    echo "System install requires root. Re-run with sudo or use --user." >&2
    exit 1
  fi
  DEST_DIR="/etc/systemd/system"
  DEST_PATH="$DEST_DIR/tuffybot@${CURRENT_USER}.service"
  echo "Installing system unit to $DEST_PATH"
  render_unit > "$DEST_PATH"
  systemctl daemon-reload
  if $ENABLE; then
    systemctl enable "tuffybot@${CURRENT_USER}.service"
  fi
  if $START; then
    systemctl start "tuffybot@${CURRENT_USER}.service"
  fi
else
  # user mode
  DEST_DIR="$HOME/.config/systemd/user"
  mkdir -p "$DEST_DIR"
  DEST_PATH="$DEST_DIR/tuffybot@${CURRENT_USER}.service"
  echo "Installing user unit to $DEST_PATH"
  render_unit > "$DEST_PATH"
  # ensure user daemon aware
  systemctl --user daemon-reload
  if $ENABLE; then
    systemctl --user enable "tuffybot@${CURRENT_USER}.service"
  fi
  if $START; then
    systemctl --user start "tuffybot@${CURRENT_USER}.service"
  fi
fi

echo "Done. Installed: $DEST_PATH"
