#!/usr/bin/env bash
set -euo pipefail

SERVICE_USER="${1:-yetaos}"

if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
  sudo useradd -r -s /bin/false "$SERVICE_USER"
fi

sudo usermod -aG lxd,video,render "$SERVICE_USER"

sudo mkdir -p \
  /srv/yetaos/models \
  /srv/yetaos/data \
  /srv/yetaos/workspaces \
  /srv/yetaos/secrets \
  /srv/yetaos/db

sudo chown -R "$SERVICE_USER":"$SERVICE_USER" /srv/yetaos
sudo chmod 0700 /srv/yetaos/secrets

echo "Host setup completed for user: $SERVICE_USER"
