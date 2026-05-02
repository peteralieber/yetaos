# pinned: code-server 4.93.1
set -e
CS_VERSION=4.93.1
DEB_PATH="/tmp/code-server_${CS_VERSION}_amd64.deb"

if ! command -v code-server >/dev/null 2>&1; then
  curl -fsSL "https://github.com/coder/code-server/releases/download/v${CS_VERSION}/code-server_${CS_VERSION}_amd64.deb" -o "${DEB_PATH}"
  dpkg -i "${DEB_PATH}"
fi

if ! id -u ubuntu >/dev/null 2>&1; then
  useradd -m -s /bin/bash ubuntu
fi

mkdir -p /home/ubuntu/.config/code-server
cat >/home/ubuntu/.config/code-server/config.yaml <<'CFG'
bind-addr: 0.0.0.0:8080
auth: none
cert: false
CFG
chown -R ubuntu:ubuntu /home/ubuntu/.config

systemctl enable --now code-server@ubuntu
