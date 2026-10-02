#!/usr/bin/env bash
set -euo pipefail

: "${AUR_SSH_PRIVATE_KEY:?Set the AUR_SSH_PRIVATE_KEY repository secret}"
: "${AUR_USERNAME:?Set the AUR_USERNAME repository variable}"
: "${AUR_EMAIL:?Set the AUR_EMAIL repository variable}"

cd "$(dirname "$0")/.."
test "$(git branch --show-current)" = main
test "$(makepkg --printsrcinfo)" = "$(cat .SRCINFO)"

git fetch origin main
if [[ $(git rev-parse HEAD) != $(git rev-parse origin/main) ]]; then
  echo 'GitHub main moved since validation; retry on the next run.' >&2
  exit 1
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
install -m 700 -d "$work/ssh"
printf '%s\n' "$AUR_SSH_PRIVATE_KEY" > "$work/ssh/aur_key"
chmod 600 "$work/ssh/aur_key"
ssh-keyscan -T 10 -t ed25519 aur.archlinux.org 2>/dev/null > "$work/ssh/known_hosts"
test -s "$work/ssh/known_hosts"
fingerprint=$(ssh-keygen -lf "$work/ssh/known_hosts" -E sha256 | awk '{print $2}')
if [[ $fingerprint != 'SHA256:RFzBCUItH9LZS0cKB5UE6ceAYhBD5C8GeOBip8Z11+4' ]]; then
  echo "Unexpected AUR SSH host fingerprint: $fingerprint" >&2
  exit 1
fi
export GIT_SSH_COMMAND="ssh -i $work/ssh/aur_key -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$work/ssh/known_hosts"

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add PKGBUILD .SRCINFO
if ! git diff --cached --quiet; then
  version=$(sed -n 's/^pkgver=//p' PKGBUILD)
  git commit -m "Update opencodex-bin to $version"
  git push origin HEAD:main
fi

git clone --branch master ssh://aur@aur.archlinux.org/opencodex-bin.git "$work/aur"
aur_version=$(sed -n 's/^pkgver=//p' "$work/aur/PKGBUILD")-$(sed -n 's/^pkgrel=//p' "$work/aur/PKGBUILD")
repo_version=$(sed -n 's/^pkgver=//p' PKGBUILD)-$(sed -n 's/^pkgrel=//p' PKGBUILD)
if [[ $(vercmp "$aur_version" "$repo_version") -gt 0 ]]; then
  echo "AUR already has newer package version $aur_version; refusing to overwrite it with $repo_version" >&2
  exit 1
fi
scripts/sync-aur.sh "$work/aur"
if ! git -C "$work/aur" diff --cached --quiet; then
  git -C "$work/aur" config user.name "$AUR_USERNAME"
  git -C "$work/aur" config user.email "$AUR_EMAIL"
  git -C "$work/aur" commit -m "Update opencodex-bin to $(sed -n 's/^pkgver=//p' PKGBUILD)"
  git -C "$work/aur" push origin HEAD:master
fi
local_head=$(git -C "$work/aur" rev-parse HEAD)
remote_head=$(git -C "$work/aur" ls-remote origin refs/heads/master | cut -f1)
if [[ $local_head != "$remote_head" ]]; then
  echo 'AUR remote HEAD does not match the published commit' >&2
  exit 1
fi
expected_version=$(sed -n 's/^pkgver=//p' PKGBUILD)-$(sed -n 's/^pkgrel=//p' PKGBUILD)
python - "$expected_version" <<'PY'
import json
import sys
import time
from urllib.request import Request, urlopen

expected = sys.argv[1]
url = 'https://aur.archlinux.org/rpc/v5/info?arg[]=opencodex-bin'
for attempt in range(12):
    with urlopen(Request(url, headers={'User-Agent': 'opencodex-bin-publisher'}), timeout=20) as response:
        data = json.load(response)
    if data['resultcount'] == 1 and data['results'][0]['Version'] == expected:
        print(f'AUR reports opencodex-bin {expected}')
        break
    time.sleep(5)
else:
    raise SystemExit(f'AUR API did not report expected version {expected}')
PY
