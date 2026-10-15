#!/bin/bash
# The lab VM's first-boot setup (EC2 user data; workbench/vm create passes it).
# Ubuntu 24.04: Python 3.12 venv at ~/lab with PyTorch CPU and the workbench
# libraries, Ollama for local models, and ~/SETUP_DONE when finished.
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-dev build-essential git curl htop tmux jq unzip
sudo -u ubuntu bash -lc 'curl -LsSf https://astral.sh/uv/install.sh | sh'
sudo -u ubuntu bash -lc '~/.local/bin/uv venv ~/lab --python 3.12 && ~/.local/bin/uv pip install --python ~/lab/bin/python torch --index-url https://download.pytorch.org/whl/cpu && ~/.local/bin/uv pip install --python ~/lab/bin/python numpy transformers datasets tokenizers tiktoken safetensors scikit-learn matplotlib jupyterlab'
sudo -u ubuntu bash -lc '[ -f ~/zts/workbench/requirements.txt ] && ~/.local/bin/uv pip install --python ~/lab/bin/python -r ~/zts/workbench/requirements.txt || true'
echo 'source ~/lab/bin/activate' >> /home/ubuntu/.bashrc
curl -fsSL https://ollama.com/install.sh | sh
mkdir -p /home/ubuntu/work && chown ubuntu:ubuntu /home/ubuntu/work
touch /home/ubuntu/SETUP_DONE && chown ubuntu:ubuntu /home/ubuntu/SETUP_DONE
