#!/usr/bin/env bash
set -euo pipefail

SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "==> Stopping and disabling voice-input service..."
systemctl --user disable --now voice-input || true

echo "==> Removing systemd unit files..."
rm -f "$SYSTEMD_DIR/voice-input.service"

echo "==> Reloading systemd daemon..."
systemctl --user daemon-reload

echo "==> Uninstalling Python package..."
if command -v pipx &>/dev/null; then
  pipx uninstall voice-input
  echo "    Uninstalled via pipx"
else
  pip uninstall -y voice-input --user
  echo "    Uninstalled via pip"
fi

echo "==> Done. Configuration and recordings in ~/.config/voice-input/ and ~/.voice-input/recordings/ were kept."
