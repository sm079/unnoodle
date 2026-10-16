#!/usr/bin/env bash
# Deletes this pod when the GPU process that rented it stops checking in, so a machine that went to sleep or lost its
# connection can't leave a GPU billing. The GPU process touches the heartbeat file over SSH every minute.
# Args: <seconds without a heartbeat before deleting>
set -euo pipefail

LIMIT="$1"
HEARTBEAT=/dev/shm/heartbeat
touch "$HEARTBEAT"

# RunPod gives every pod its own id and a key that can only act on that pod, in the container's environment
env_of_pod() { tr '\0' '\n' < /proc/1/environ | sed -n "s/^$1=//p"; }
POD_ID="$(env_of_pod RUNPOD_POD_ID)"
KEY="$(env_of_pod RUNPOD_API_KEY)"
[ -n "$POD_ID" ] && [ -n "$KEY" ] || { echo "No pod id or pod key in the environment" >&2; exit 1; }

cat > /dev/shm/watchdog-loop.sh <<LOOP
#!/usr/bin/env bash
while sleep 30; do
  age=\$(( \$(date +%s) - \$(stat -c %Y "$HEARTBEAT") ))
  if [ "\$age" -gt "$LIMIT" ]; then
    echo "No heartbeat for \${age}s at \$(date -u +%FT%TZ); deleting pod $POD_ID"
    curl -fsS -X DELETE "https://rest.runpod.io/v1/pods/$POD_ID" -H "Authorization: Bearer $KEY" \
      || runpodctl remove pod "$POD_ID"
  fi
done
LOOP
pkill -f watchdog-loop.sh 2>/dev/null || true
setsid nohup bash /dev/shm/watchdog-loop.sh > /dev/shm/watchdog.log 2>&1 < /dev/null &
echo "Watchdog on: the pod deletes itself after ${LIMIT}s without a heartbeat"
