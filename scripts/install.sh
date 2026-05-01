#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

sudo bash "$ROOT_DIR/scripts/host-setup.sh" yetaos

sudo mkdir -p /etc/yetaos
if [[ ! -f /etc/yetaos/.env ]]; then
  sudo cp "$ROOT_DIR/backend/.env.example" /etc/yetaos/.env
  sudo chmod 0600 /etc/yetaos/.env
fi

cd "$ROOT_DIR/backend"
uv sync --all-groups

sudo cp "$ROOT_DIR/deploy/yetaos-backend.service" /etc/systemd/system/yetaos-backend.service
sudo cp "$ROOT_DIR/deploy/Caddyfile" /etc/caddy/Caddyfile || true
sudo systemctl daemon-reload
sudo systemctl enable --now yetaos-backend.service

echo "Installation complete"
