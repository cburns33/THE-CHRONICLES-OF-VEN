#!/usr/bin/env bash
# Install and start systemd services for the API and UI.
# Run as root from the project directory.
set -euo pipefail

PROJECT_DIR="/opt/inherited-cloud"

echo "Installing systemd services…"

cp "$PROJECT_DIR/deploy/services/novel-api.service" /etc/systemd/system/
cp "$PROJECT_DIR/deploy/services/novel-ui.service"  /etc/systemd/system/

systemctl daemon-reload

systemctl enable novel-api
systemctl enable novel-ui

systemctl restart novel-api
systemctl restart novel-ui

echo ""
echo "Services installed and started."
echo "  Check API : systemctl status novel-api"
echo "  Check UI  : systemctl status novel-ui"
echo "  View logs : journalctl -u novel-api -f"
