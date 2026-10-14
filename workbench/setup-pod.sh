#!/bin/sh
# Run once per pod, on the pod:  sh /workspace/zts/workbench/setup-pod.sh
# The venv, model weights and datasets live on the network volume
# (/workspace), so a fresh pod reuses them and starts in about a minute.
set -eu
W=/workspace
export HF_HOME=$W/hf                      # model downloads survive the pod
if [ ! -x $W/venv/bin/python ]; then
  python3 -m venv $W/venv
  $W/venv/bin/pip install -q --upgrade pip
fi
$W/venv/bin/pip install -q -r $W/zts/workbench/requirements.txt
$W/venv/bin/pip install -q -r $W/zts/workbench/requirements-gpu.txt
grep -q 'zts workbench' ~/.bashrc 2>/dev/null || cat >> ~/.bashrc <<'RC'
# zts workbench
export HF_HOME=/workspace/hf
. /workspace/venv/bin/activate
cd /workspace/zts
RC
# Stop the pod after WB_IDLE_MIN minutes with the GPU idle and nobody logged in.
pkill -f idle-stop.sh 2>/dev/null || true
nohup sh $W/zts/workbench/idle-stop.sh > $W/idle-stop.log 2>&1 &
$W/venv/bin/python -c "import torch; print('torch', torch.__version__, '| GPU:', torch.cuda.get_device_name(0))"
echo "ready. Open a new shell (or: . ~/.bashrc). Idle stop after ${WB_IDLE_MIN:-30} min."
