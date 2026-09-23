#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/opencodex-bin-aur-checkout" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
aur_dir="$(realpath "$1")"

if [[ ! -d "$aur_dir/.git" ]]; then
  echo "Not a Git checkout: $aur_dir" >&2
  exit 1
fi
if [[ -n "$(git -C "$aur_dir" status --porcelain)" ]]; then
  echo "AUR checkout has uncommitted changes: $aur_dir" >&2
  exit 1
fi

expected="$(cd "$repo_root" && makepkg --printsrcinfo)"
actual="$(cat "$repo_root/.SRCINFO")"
if [[ "$expected" != "$actual" ]]; then
  echo 'Stale .SRCINFO; run makepkg --printsrcinfo > .SRCINFO first' >&2
  exit 1
fi

for file in PKGBUILD .SRCINFO ocx-launcher LICENSE; do
  cp "$repo_root/$file" "$aur_dir/$file"
done
git -C "$aur_dir" add PKGBUILD .SRCINFO ocx-launcher LICENSE
git -C "$aur_dir" status --short
echo 'Review the staged AUR files, then commit and push from the AUR checkout.'
