#!/usr/bin/env bash
set -euo pipefail

: "${AUR_SSH_PRIVATE_KEY:?AUR publication is disabled: set the AUR_SSH_PRIVATE_KEY repository secret}"
: "${AUR_USERNAME:?AUR publication is disabled: set the AUR_USERNAME repository variable}"
: "${AUR_EMAIL:?AUR publication is disabled: set the AUR_EMAIL repository variable}"

if [[ $(id -u) -eq 0 ]]; then
  echo 'Run this script as an unprivileged user: makepkg refuses to run as root.' >&2
  exit 1
fi

cd "$(dirname "$0")/.."

# actions/checkout silently downloads a tarball instead of a Git checkout when git
# is missing, which used to abort here with a bare "not a git repository" message.
if [[ ! -d .git ]]; then
  echo "Not a Git checkout: $(pwd)" >&2
  echo 'Install git before actions/checkout so the recipe can be committed and pushed.' >&2
  exit 1
fi

branch=$(git branch --show-current)
if [[ $branch != main ]]; then
  echo "Publishing requires the main branch; the current branch is '${branch:-detached HEAD}'" >&2
  exit 1
fi

if [[ ! -f .SRCINFO ]]; then
  echo '.SRCINFO is missing; regenerate it with: makepkg --printsrcinfo > .SRCINFO' >&2
  exit 1
fi
if ! srcinfo=$(makepkg --printsrcinfo); then
  echo 'makepkg could not generate .SRCINFO metadata; refusing to publish.' >&2
  exit 1
fi
if [[ $srcinfo != "$(<.SRCINFO)" ]]; then
  echo 'Stale .SRCINFO; regenerate it with: makepkg --printsrcinfo > .SRCINFO' >&2
  exit 1
fi

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
attempts = 30

# The AUR metadata API can keep serving the previous version for a few minutes
# after the Git push, so poll patiently instead of failing the run too early.
for attempt in range(1, attempts + 1):
    reported = 'unavailable'
    try:
        with urlopen(Request(url, headers={'User-Agent': 'opencodex-bin-publisher'}), timeout=20) as response:
            data = json.load(response)
        if data.get('resultcount') == 1:
            reported = data['results'][0]['Version']
    except Exception as error:  # transient API or network failure; keep polling
        reported = f'error: {error}'
    print(f'AUR metadata check {attempt}/{attempts}: {reported}', flush=True)
    if reported == expected:
        print(f'AUR reports opencodex-bin {expected}')
        break
    time.sleep(10)
else:
    raise SystemExit(
        f'AUR still reports {reported} instead of {expected} after {attempts} checks'
    )
PY
