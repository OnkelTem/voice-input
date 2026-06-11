#!/usr/bin/env bash
set -euo pipefail

echo "Stopping and disabling voice-input.service..."
systemctl --user disable --now voice-input 2>/dev/null || true

rm -f ~/.config/systemd/user/voice-input.service
systemctl --user daemon-reload

echo "Service removed."
