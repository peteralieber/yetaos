# pinned: Blender 4.1 LTS from blender.org; checksum verified
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
    libx11-6 \
    libxi6 \
    libxxf86vm1 \
    libxfixes3 \
    libxrender1 \
    libgl1-mesa-glx \
    libglu1-mesa \
    wget \
    xz-utils

BLENDER_VERSION="4.1.1"
BLENDER_URL="https://download.blender.org/release/Blender4.1/blender-${BLENDER_VERSION}-linux-x64.tar.xz"
BLENDER_CHECKSUM="da9bce89f7e0b67cc6069a0bd00a4f55c9cdcc2a"

cd /opt
wget -q "${BLENDER_URL}" -O blender.tar.xz
echo "${BLENDER_CHECKSUM}  blender.tar.xz" | sha1sum -c -
tar -xJf blender.tar.xz
rm blender.tar.xz
mv blender-${BLENDER_VERSION}-linux-x64 blender

ln -s /opt/blender/blender /usr/local/bin/blender
