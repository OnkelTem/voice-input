#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "Linking voice-input.service..."
systemctl --user link "$DIR/systemd/voice-input.service"

systemctl --user daemon-reload
echo "Enabling and starting service..."
systemctl --user enable --now voice-input

systemctl --user status voice-input --no-pager
