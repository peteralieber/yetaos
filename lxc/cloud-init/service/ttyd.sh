# pinned: ttyd 1.7.7 from GitHub release
set -e
TTYD_VERSION=1.7.7

if [[ ! -x /usr/local/bin/ttyd ]]; then
  curl -fsSL "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.x86_64" -o /usr/local/bin/ttyd
  chmod +x /usr/local/bin/ttyd
fi

cat >/etc/systemd/system/ttyd.service <<'UNIT'
[Unit]
Description=ttyd terminal over web
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/ttyd -W -p 7681 /bin/bash -l
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now ttyd.service
