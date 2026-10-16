#!/usr/bin/env bash
# Downloads model files into the renderer's models folder (app.gpu.files says which, and from where).
# Args: one or more "repo::folder::path1,path2,..." specs. Files go into models/<folder>; with an empty folder the
# repo's paths already mirror models/ (diffusion_models/, text_encoders/, vae/, loras/). A repo that is an https://
# URL is a plain file host: each path is fetched from <url>/<path>.
# HF_TOKEN, when set at the top of the piped script, unlocks gated Hugging Face repos.
set -euo pipefail

DIR="$(cat /root/.renderer_dir 2>/dev/null || true)"
[ -n "$DIR" ] && [ -d "$DIR/models" ] || { echo "Renderer folder unknown; run setup first" >&2; exit 1; }

if ! command -v hf >/dev/null 2>&1; then
  pip install -q -U "huggingface_hub[hf_xet]"
fi
export HF_XET_HIGH_PERFORMANCE=1

for spec in "$@"; do
  repo="${spec%%::*}"
  rest="${spec#*::}"
  folder="${rest%%::*}"
  IFS=',' read -r -a files <<< "${rest#*::}"
  dest="$DIR/models${folder:+/$folder}"
  echo "$repo (${#files[@]} files) -> $dest"
  if [[ "$repo" == https://* ]]; then
    mkdir -p "$dest"
    for f in "${files[@]}"; do
      [ -s "$dest/$f" ] && continue
      curl -fsSL --retry 3 -o "$dest/$f.part" "$repo/$f"
      mv "$dest/$f.part" "$dest/$f"
    done
  else
    HF_TOKEN="${HF_TOKEN:-}" hf download "$repo" "${files[@]}" --local-dir "$dest" >/dev/null
  fi
done
