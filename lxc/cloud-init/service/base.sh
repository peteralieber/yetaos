# pinned: ubuntu packages from distro repository
set -e
mkdir -p /workspace /models /data
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y curl git ca-certificates sudo htop jq build-essential
