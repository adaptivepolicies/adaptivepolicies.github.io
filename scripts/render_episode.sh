#!/usr/bin/env bash
# Start the VirtualHome player headless and replay the demo episode with recording on.
# Run in WSL:  bash scripts/render_episode.sh <AdaptPolicies checkout> <initial_state.json> <output dir>
# VIRTUALHOME_SIM_ROOT must hold the player matching the evaluation build
# (Assembly-CSharp.dll f6e9e561..., AdaptPolicies.NativeRepairs.dll f1738849...).
set -euo pipefail
repo=$(cd "$1" && pwd); state=$(realpath "$2"); out=$(realpath -m "$3")
site=$(cd "$(dirname "$0")/.." && pwd)
sim=${VIRTUALHOME_SIM_ROOT:?Set VIRTUALHOME_SIM_ROOT}
port=${SIM_PORT:-8085}
vh=$repo/src/virtual_home
export PYTHONPATH=$repo/src:$vh:$vh/virtualhome/src:$vh/virtualhome/src/virtualhome:$vh/virtualhome/src/virtualhome/simulation
mkdir -p "$out"
xvfb-run -a --server-args="-screen 0 1280x720x24" "$sim/linux_exec.v2.3.0.x86_64" -force-glcore -batchmode \
  "-http-port=$port" -logFile "$out/Player.log" > "$out/simulator-stdout.log" 2>&1 &
sim_pid=$!
trap 'pkill -P "$sim_pid" 2>/dev/null; kill "$sim_pid" 2>/dev/null || true' EXIT
for _ in $(seq 1 120); do
  curl -s -o /dev/null "http://127.0.0.1:$port" && break
  sleep 1
done
source ~/miniforge3/etc/profile.d/conda.sh
conda activate research_proj
SIM_PORT=$port python "$site/scripts/render_episode.py" --initial-state "$state" --output "$out/frames" "${@:4}"
