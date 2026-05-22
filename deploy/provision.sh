#!/usr/bin/env bash
# =============================================================================
# VPS Provisioning Script — IONOS Ubuntu 22.04
# Run once as root after SSH-ing into your new server.
#
# Usage:
#   ssh root@YOUR_VPS_IP
#   bash provision.sh
# =============================================================================

set -euo pipefail

PROJECT_DIR="/opt/inherited-cloud"
SERVICE_USER="novel"
PYTHON_VERSION="3.11"

echo "=== Inherited Cloud — VPS Provisioning ==="

# 1. Update system
apt-get update -qq && apt-get upgrade -y -qq

# 2. Install dependencies
apt-get install -y -qq \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-venv \
    python3-pip \
    nginx \
    git \
    curl \
    unzip

# 3. Add swap (1 GB — critical for 1 GB RAM VPS)
if [ ! -f /swapfile ]; then
    fallocate -l 1G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "Swap file created (1 GB)"
else
    echo "Swap already exists — skipping"
fi

# 4. Create a non-root service user
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -r -m -s /bin/bash "$SERVICE_USER"
    echo "Created user: $SERVICE_USER"
fi

# 5. Create project directory
mkdir -p "$PROJECT_DIR"
chown "$SERVICE_USER":"$SERVICE_USER" "$PROJECT_DIR"

echo ""
echo "=== Provisioning complete ==="
echo ""
echo "Next steps:"
echo "  1. Copy your project to ${PROJECT_DIR}:"
echo "     scp -r . root@YOUR_VPS_IP:${PROJECT_DIR}"
echo "  2. Set up the Python environment:"
echo "     cd ${PROJECT_DIR} && bash deploy/setup_venv.sh"
echo "  3. Copy and fill in your .env file"
echo "  4. Install systemd services:"
echo "     bash deploy/install_services.sh"
echo "  5. Install cron job:"
echo "     crontab -u ${SERVICE_USER} deploy/crontab.txt"
echo "  6. Run setup:"
echo "     sudo -u ${SERVICE_USER} ${PROJECT_DIR}/.venv/bin/python scripts/setup.py"
