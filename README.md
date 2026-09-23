# OpenCodeX AUR package

This repository packages the stable [OpenCodeX](https://opencodex.me/zh-cn/getting-started/installation/) standalone Linux release as `opencodex-bin` for Arch Linux. The executable includes Bun, so this package does not install Node.js, npm, or Bun separately. It provides both `ocx` and `opencodex` commands and keeps the release's `gui/dist` next to the executable under `/usr/lib/opencodex`.

## Repository layout

| File | Purpose |
| --- | --- |
| `PKGBUILD`, `.SRCINFO` | AUR build recipe and matching AUR metadata |
| `ocx-launcher`, `LICENSE` | Files included in the AUR source checkout |
| `scripts/sync-aur.sh` | Copies only the four AUR files to a separate AUR checkout |
| `README.md`, `.gitignore` | GitHub documentation and local build exclusions |

The GitHub repository is the maintenance source. The AUR checkout contains only `PKGBUILD`, `.SRCINFO`, `ocx-launcher`, and `LICENSE`; generated archives, build directories, and packages stay out of both repositories.

## Build locally

Install Arch's `base-devel` tools, then run from this repository:

```sh
makepkg -si
ocx --version
opencodex --version
```

The package supports `x86_64` and `aarch64`. The 2.63.0-2 release was installed and run on x86_64; aarch64 remains untested on real hardware. Before using OpenCodeX with Codex, install a Codex client separately and follow the [OpenCodeX quick start](https://opencodex.me/zh-cn/getting-started/quickstart/) to set up a provider. Use AUR package upgrades for new versions; `ocx update` is an upstream self-updater and should not be used on files managed by pacman.

## Update and publish

1. Change `pkgver` in `PKGBUILD` to a stable upstream release and reset `pkgrel` to `1`. For packaging-only changes, increment `pkgrel`.
2. Update both architecture-specific SHA-256 values from the [release assets](https://github.com/lidge-jun/opencodex/releases), then regenerate metadata:

   ```sh
   makepkg --printsrcinfo > .SRCINFO
   makepkg --verifysource
   makepkg -s
   namcap PKGBUILD
   ```

3. Commit and push this repository to your GitHub remote.
   If this directory is not yet a Git repository, initialize it with `git init -b main`, commit the files, then add your own GitHub repository as `origin` and push `main`.
4. Clone the AUR package as a separate checkout after confirming the `opencodex-bin` name is available and configuring AUR SSH access:

   ```sh
   git clone ssh://aur@aur.archlinux.org/opencodex-bin.git ../opencodex-bin-aur
   ./scripts/sync-aur.sh ../opencodex-bin-aur
   cd ../opencodex-bin-aur
   git diff --cached
   git commit -m 'Update opencodex-bin package'
   git push origin master
   ```

The sync script stages only the AUR files and stops if the AUR checkout has local changes or `.SRCINFO` is stale. It leaves the final commit and push to the maintainer.

## Sources

- [OpenCodeX installation guide](https://opencodex.me/zh-cn/getting-started/installation/)
- [Upstream releases](https://github.com/lidge-jun/opencodex/releases)
- [Arch AUR submission guidelines](https://wiki.archlinux.org/title/AUR_submission_guidelines)

The `LICENSE` file is copied from the [OpenCodeX upstream repository](https://github.com/lidge-jun/opencodex/blob/main/LICENSE).
