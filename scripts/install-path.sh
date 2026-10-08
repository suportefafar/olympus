#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source="$script_dir/../olymctl"
target="/usr/local/bin/olymctl"
[[ -x "$source" ]] || { echo "olymctl executable not found: $source" >&2; exit 1; }
case ":$PATH:" in *:/usr/local/bin:*) ;; *) echo "/usr/local/bin is not in PATH" >&2; exit 1;; esac
if [[ -e "$target" || -L "$target" ]]; then
  current="$(readlink -f -- "$target" 2>/dev/null || true)"
  [[ "$current" == "$source" ]] && { echo "Already installed: $target -> $source"; exit 0; }
  echo "Refusing to replace existing path: $target" >&2; exit 1
fi
ln -s -- "$source" "$target"
[[ "$(readlink -f -- "$target")" == "$source" ]] || { echo "Installed link did not resolve correctly" >&2; exit 1; }
echo "Installed $target -> $source"
