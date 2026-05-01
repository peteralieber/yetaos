# pinned: torch 2.3.0 ROCm 6.1 wheels
set -e
python3 -m pip install --no-cache-dir torch==2.3.0+rocm6.1 --index-url https://download.pytorch.org/whl/rocm6.1
