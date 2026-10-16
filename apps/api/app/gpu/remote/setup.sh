#!/usr/bin/env bash
# Prepares the template's renderer on a fresh pod: pins its release, then restarts it so that it listens on localhost
# only (reached through the SSH tunnel), keeps inputs, outputs and temporary files in RAM (/dev/shm), never on the
# pod's disk, and comes back by itself if it exits.
# Args: <release tag>
set -euo pipefail

DIR=/workspace/runpod-slim/ComfyUI
ARGS_FILE=/workspace/runpod-slim/comfyui_args.txt
RAM=/dev/shm/renderer
PORT=8188
RELEASE="$1"

[ -d "$DIR" ] || { echo "Renderer not found at $DIR" >&2; exit 1; }
echo "$DIR" > /root/.renderer_dir
cd "$DIR"
# The venv is named after the template's CUDA version (.venv-cu128, .venv-cu130, ...)
VENV="$(ls -d .venv-cu* 2>/dev/null | grep -v '\.bak' | sort | tail -1)"
[ -n "$VENV" ] || { echo "No venv in $DIR" >&2; exit 1; }

current="$(git describe --tags --exact-match 2>/dev/null || git rev-parse --short HEAD)"
if [ "$current" != "$RELEASE" ]; then
  echo "Renderer $current -> $RELEASE"
  git fetch --quiet --tags --force origin
  git -c advice.detachedHead=false checkout --quiet "$RELEASE"
  "$VENV/bin/python" -m pip install -q -r requirements.txt
fi

mkdir -p "$RAM"/{input,output,temp,user,tmp}
chmod 700 "$RAM"
{
  echo "--listen 127.0.0.1"
  echo "--input-directory $RAM/input"
  echo "--output-directory $RAM/output"
  echo "--temp-directory $RAM/temp"
  echo "--user-directory $RAM/user"
  echo "--fast-disk"
} > "$ARGS_FILE"

# Nothing else the template runs is used, and nothing else should listen
pkill -x filebrowser 2>/dev/null || true
pkill -f jupyter-lab 2>/dev/null || true
if pkill -f "python main.py" 2>/dev/null; then
  for _ in $(seq 30); do pgrep -f "python main.py" >/dev/null || break; sleep 1; done
fi

cat > "$RAM/run.sh" <<RUN
#!/usr/bin/env bash
cd "$DIR"
source "$VENV/bin/activate"
export TMPDIR="$RAM/tmp"
mapfile -t EXTRA < <(tr -s '[:space:]' '\n' < "$ARGS_FILE" | sed '/^\$/d')
while :; do
  python main.py --port "$PORT" "\${EXTRA[@]}"
  echo "renderer exited with code \$? at \$(date -u +%FT%TZ); restarting in 3s"
  sleep 3
done
RUN
# /dev/shm is mounted noexec, so the script runs through bash
setsid nohup bash "$RAM/run.sh" > "$RAM/renderer.log" 2>&1 < /dev/null &

for i in $(seq 180); do
  if curl -fs "http://127.0.0.1:$PORT/system_stats" >/dev/null; then
    echo "Renderer ready after ${i}s"
    exit 0
  fi
  sleep 1
done
echo "Renderer didn't start; last log lines:" >&2
tail -30 "$RAM/renderer.log" >&2
exit 1
