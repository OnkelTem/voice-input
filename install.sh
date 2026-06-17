#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SYSTEMD_DIR="$HOME/.config/systemd/user"
SERVICE_SRC="$SCRIPT_DIR/systemd/voice-input.service"

# Check dependencies
for cmd in python3 xdotool; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "ERROR: $cmd not found. Install it first."
    echo "  xdotool: sudo apt install xdotool"
    exit 1
  fi
done

# Generate static assets
make -C "$SCRIPT_DIR" static
echo "✓ Static assets generated"

# Install Python package
if command -v pipx &>/dev/null; then
  if pipx install --editable "$SCRIPT_DIR" --force 2>/dev/null; then
    echo "✓ Installed via pipx (editable)"
  else
    # fallback для старых версий pipx (<1.2.0)
    pipx install "$SCRIPT_DIR" --force
    echo "✓ Installed via pipx"
  fi
else
  echo "pipx not found, installing via pip --user"
  pip install --user -e "$SCRIPT_DIR"
  echo "✓ Installed via pip"
fi

# Deploy systemd service
mkdir -p "$SYSTEMD_DIR"
cp "$SERVICE_SRC" "$SYSTEMD_DIR/"
echo "✓ Systemd service deployed"

# Enable and start
systemctl --user daemon-reload
systemctl --user enable --now voice-input
systemctl --user status voice-input --no-pager
echo "✓ Service enabled and started"
