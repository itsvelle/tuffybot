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

# Determine the target user for user-mode installs. If the script is run as root
# and SUDO_USER is set, prefer that user so the unit is installed into their
# home and systemctl --user is invoked as that user. Otherwise use the current
# effective user.
TARGET_USER="$CURRENT_USER"
if [[ "$MODE" == "user" && $(id -u) -eq 0 ]]; then
  if [[ -n "${SUDO_USER:-}" ]]; then
    TARGET_USER="$SUDO_USER"
  else
    # No SUDO_USER: default to root (may not have a user bus)
    TARGET_USER="root"
  fi
fi

# Resolve UID and home directory for target user
if ! TARGET_UID="$(id -u "$TARGET_USER" 2>/dev/null)"; then
  echo "Cannot determine UID for user: $TARGET_USER" >&2
  exit 1
fi
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6 || true)"
if [[ -z "$TARGET_HOME" ]]; then
  # fallback
  TARGET_HOME="$(eval echo ~${TARGET_USER})"
fi

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
  # Replace %i with the target username in a safe way
  sed "s|%i|${TARGET_USER}|g" "$UNIT_SRC"
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
  # user mode
  DEST_DIR="$TARGET_HOME/.config/systemd/user"
  mkdir -p "$DEST_DIR"
  DEST_PATH="$DEST_DIR/tuffybot@${TARGET_USER}.service"
  echo "Installing user unit to $DEST_PATH"

  # Write the unit file. If we're root installing to another user's home,
  # write the file as that user so ownership/permissions are correct.
  if [[ $(id -u) -eq 0 && "$TARGET_USER" != "$CURRENT_USER" ]]; then
    sed "s|%i|${TARGET_USER}|g" "$UNIT_SRC" | sudo -u "$TARGET_USER" tee "$DEST_PATH" >/dev/null
  else
    render_unit > "$DEST_PATH"
  fi

  # Ensure XDG_RUNTIME_DIR is set so systemctl --user can talk to the user bus.
  # Prefer an existing /run/user/<uid> if available.
  if [[ -z "${XDG_RUNTIME_DIR:-}" && -d "/run/user/$TARGET_UID" ]]; then
    export XDG_RUNTIME_DIR="/run/user/$TARGET_UID"
  fi

  # Invoke systemctl --user as the target user when necessary. When running as
  # root for another user, use sudo -u and pass XDG_RUNTIME_DIR so systemctl
  # can connect to the per-user bus.
  if [[ $(id -u) -eq 0 && "$TARGET_USER" != "$CURRENT_USER" ]]; then
    if [[ -d "/run/user/$TARGET_UID" ]]; then
      sudo -u "$TARGET_USER" XDG_RUNTIME_DIR="/run/user/$TARGET_UID" systemctl --user daemon-reload
      if $ENABLE; then
        sudo -u "$TARGET_USER" XDG_RUNTIME_DIR="/run/user/$TARGET_UID" systemctl --user enable "tuffybot@${TARGET_USER}.service"
      fi
      if $START; then
        sudo -u "$TARGET_USER" XDG_RUNTIME_DIR="/run/user/$TARGET_UID" systemctl --user start "tuffybot@${TARGET_USER}.service"
      fi
    else
      echo "Warning: /run/user/$TARGET_UID not found; cannot contact user bus for $TARGET_USER." >&2
      echo "You may need to run this as $TARGET_USER while they are logged in to enable/start the unit." >&2
    fi
  else
    # normal non-root path: current user is the target user
    # Ensure XDG_RUNTIME_DIR is set even for non-root, in case the user
    # hasn't logged in via a session manager that would set it.
    if [[ -z "${XDG_RUNTIME_DIR:-}" && -d "/run/user/$TARGET_UID" ]]; then
      export XDG_RUNTIME_DIR="/run/user/$TARGET_UID"
    fi
    
    # If /run/user/<uid> doesn't exist (common on headless servers), try to create it
    # with proper permissions so systemctl --user can use it.
    if [[ -z "${XDG_RUNTIME_DIR:-}" && ! -d "/run/user/$TARGET_UID" ]]; then
      if sudo mkdir -p "/run/user/$TARGET_UID" 2>/dev/null && \
         sudo chmod 700 "/run/user/$TARGET_UID" 2>/dev/null && \
         sudo chown "$TARGET_UID:$TARGET_UID" "/run/user/$TARGET_UID" 2>/dev/null; then
        export XDG_RUNTIME_DIR="/run/user/$TARGET_UID"
        echo "Created runtime directory: $XDG_RUNTIME_DIR"
      fi
    fi
    
    # If XDG_RUNTIME_DIR is still unset, fall back to systemd-run
    if [[ -z "${XDG_RUNTIME_DIR:-}" ]]; then
      echo "Warning: XDG_RUNTIME_DIR not set and could not create /run/user/$TARGET_UID." >&2
      echo "Falling back to systemd-run for enable/start operations." >&2
      
      if $ENABLE || $START; then
        # Use systemd-run to invoke systemctl --user in a user context
        if $ENABLE; then
          systemd-run --user --scope systemctl --user enable "tuffybot@${TARGET_USER}.service" || true
        fi
        if $START; then
          systemd-run --user --scope systemctl --user start "tuffybot@${TARGET_USER}.service" || true
        fi
      fi
    else
      # Normal path: XDG_RUNTIME_DIR is set
      systemctl --user daemon-reload
      if $ENABLE; then
        systemctl --user enable "tuffybot@${TARGET_USER}.service"
      fi
      if $START; then
        systemctl --user start "tuffybot@${TARGET_USER}.service"
      fi
    fi
  fi
fi

echo "Done. Installed: $DEST_PATH"
