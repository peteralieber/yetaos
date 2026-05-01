# pinned: python 3.11 from deadsnakes, uv 0.6.10
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update
apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip
python3 -m pip install --no-cache-dir --upgrade uv==0.6.10
