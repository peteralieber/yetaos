# default: latest python3 from Ubuntu repos; version pinned at container creation time
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-dev python3-pip
python3 -m pip install --no-cache-dir --upgrade uv
