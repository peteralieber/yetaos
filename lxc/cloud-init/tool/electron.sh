# default: electron installed globally; display libs pinned from Ubuntu repos
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    xvfb

npm install -g electron --unsafe-perm=true --allow-root
