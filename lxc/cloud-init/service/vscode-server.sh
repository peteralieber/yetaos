# pinned: code-server 4.93.1
set -e
CS_VERSION=4.93.1
DEB_PATH="/tmp/code-server_${CS_VERSION}_amd64.deb"
command -v code-server >/dev/null 2>&1 || (curl -fsSL "https://github.com/coder/code-server/releases/download/v${CS_VERSION}/code-server_${CS_VERSION}_amd64.deb" -o "${DEB_PATH}" && dpkg -i "${DEB_PATH}")
id -u ubuntu >/dev/null 2>&1 || useradd -m -s /bin/bash ubuntu
mkdir -p /home/ubuntu/.config/code-server
printf '%s\n' 'bind-addr: 0.0.0.0:8080' 'auth: none' 'cert: false' >/home/ubuntu/.config/code-server/config.yaml
chown -R ubuntu:ubuntu /home/ubuntu/.config
systemctl enable --now code-server@ubuntu
