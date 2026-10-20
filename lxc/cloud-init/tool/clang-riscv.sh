# pinned: clang-18 and riscv64-linux-gnu cross toolchain from Ubuntu repos
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
    clang-18 \
    lld-18 \
    llvm-18 \
    gcc-riscv64-linux-gnu \
    g++-riscv64-linux-gnu \
    binutils-riscv64-linux-gnu \
    qemu-user-static \
    cmake \
    ninja-build \
    pkg-config

update-alternatives --install /usr/bin/clang clang /usr/bin/clang-18 100
update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-18 100
update-alternatives --install /usr/bin/lld lld /usr/bin/lld-18 100
