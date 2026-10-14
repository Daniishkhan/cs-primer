#!/bin/sh
# Stops this pod when the GPU has been idle (under 5% use) and nobody has been
# logged in for WB_IDLE_MIN minutes, so a forgotten pod cannot run up a bill.
# Uses the pod-scoped RUNPOD_API_KEY and RUNPOD_POD_ID that RunPod sets.
LIMIT=${WB_IDLE_MIN:-30}
idle=0
while :; do
  sleep 60
  util=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | sort -n | tail -1)
  # Containers often keep no login records, so count live SSH sessions.
  users=$(pgrep -f 'sshd: .*@' 2>/dev/null | wc -l)
  if [ "${util:-0}" -lt 5 ] && [ "$users" -eq 0 ]; then idle=$((idle + 1)); else idle=0; fi
  if [ "$idle" -ge "$LIMIT" ]; then
    echo "$(date) idle for $LIMIT min: stopping pod $RUNPOD_POD_ID"
    curl -fsS -X POST "https://rest.runpod.io/v1/pods/$RUNPOD_POD_ID/stop" \
      -H "Authorization: Bearer $RUNPOD_API_KEY" && exit 0
  fi
done
