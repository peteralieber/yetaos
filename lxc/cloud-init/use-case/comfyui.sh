# pinned: ComfyUI at a fixed git commit; model weights are mounted separately
set -e
COMFYUI_COMMIT="e3df71c"
COMFYUI_REPO="https://github.com/comfyanonymous/ComfyUI.git"

apt-get update
apt-get install -y git libgl1-mesa-glx libglib2.0-0

git clone "${COMFYUI_REPO}" /workspace/ComfyUI
cd /workspace/ComfyUI
git checkout "${COMFYUI_COMMIT}"

python3 -m pip install --no-cache-dir -r requirements.txt
