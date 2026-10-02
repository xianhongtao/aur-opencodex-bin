# OpenCodeX AUR package

This repository packages the stable [OpenCodeX](https://opencodex.me/zh-cn/getting-started/installation/) standalone Linux release as `opencodex-bin` for Arch Linux. The executable includes Bun, so this package does not install Node.js, npm, or Bun separately. It provides both `ocx` and `opencodex` commands and keeps the release's `gui/dist` next to the executable under `/usr/lib/opencodex`.

## Repository layout

| File | Purpose |
| --- | --- |
| `PKGBUILD`, `.SRCINFO` | AUR build recipe and matching AUR metadata |
| `ocx-launcher`, `LICENSE` | Files included in the AUR source checkout |
| `scripts/sync-aur.sh` | Copies only the four AUR files to a separate AUR checkout |
| `scripts/update-upstream.py`, `scripts/publish-aur.sh` | Verify upstream releases and publish validated changes |
| `.github/workflows/update-aur.yml` | Scheduled and manual GitHub Actions update |
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

## Automatic updates and publication

The [update workflow](.github/workflows/update-aur.yml) checks every six hours at 02:23, 08:23, 14:23 and 20:23 Asia/Shanghai. GitHub may delay scheduled runs. It can also be started with **Actions → Update OpenCodeX AUR package → Run workflow**. A push to `main` that changes the package or its publication scripts triggers the same validation. GitHub may disable scheduled workflows after 60 days without repository activity; re-enable the workflow in Actions if that happens.

The updater accepts only a newer stable release. It downloads both Linux archives and their upstream `.sha256` files, verifies the hashes and archive layout, then regenerates `.SRCINFO`. The Arch validation job builds and installs the x86_64 package and runs `ocx --version` and `opencodex --version`. It inspects aarch64 archives but does not run aarch64 binaries on real hardware. Failed checks stop publication.

Both jobs install the Arch toolchain before checking out the repository, so the workflow always works on a real Git checkout that it can commit to. The publication step also drops to an unprivileged user, because `makepkg` refuses to run as root. If a prerequisite is missing, the job stops with an explicit message instead of a bare Git error.

To enable automatic AUR publication:

1. Generate a dedicated unencrypted Ed25519 SSH key for this workflow and add its **public** key to your [AUR account](https://aur.archlinux.org/account/) under SSH Public Key. Store its private key, including the first and last lines, as the GitHub Actions repository secret `AUR_SSH_PRIVATE_KEY`. Do not reuse a personal SSH key.
2. Set GitHub Actions repository variables `AUR_USERNAME` and `AUR_EMAIL` to the AUR commit identity you want recorded. In repository **Settings → Actions → General**, allow workflow `GITHUB_TOKEN` read and write access to repository contents. If `main` is protected, allow the workflow identity to push to it or adjust the branch rule.
3. Start the workflow manually and inspect both the GitHub `main` commit and the [AUR package](https://aur.archlinux.org/packages/opencodex-bin). Until the SSH secret and AUR account key are configured, the publication job fails with a setup message; do not treat a passing validation job as a published update.

The workflow checks the [officially announced AUR Ed25519 host fingerprint](https://archlinux.org/news/aur-migration-new-ssh-hostkeys/) before connecting and uses strict SSH host verification. Only the publication job receives the AUR private key. It commits the validated recipe to GitHub, then sends only `PKGBUILD`, `.SRCINFO`, `ocx-launcher`, and `LICENSE` to AUR. If the GitHub push succeeds and the AUR push fails, the next scheduled or manual run compares AUR with the current recipe and retries. An unchanged package produces no commit. To pause updates, disable this workflow in the repository's Actions tab.

For a manual packaging-only change, increment `pkgrel`, regenerate `.SRCINFO` with `makepkg --printsrcinfo > .SRCINFO`, and push to `main`. For a local AUR checkout, `./scripts/sync-aur.sh ../opencodex-bin-aur` stages only the four AUR files after checking that `.SRCINFO` is current and the checkout is clean.

## Sources

- [OpenCodeX installation guide](https://opencodex.me/zh-cn/getting-started/installation/)
- [Upstream releases](https://github.com/lidge-jun/opencodex/releases)
- [Arch AUR submission guidelines](https://wiki.archlinux.org/title/AUR_submission_guidelines)

The `LICENSE` file is copied from the [OpenCodeX upstream repository](https://github.com/lidge-jun/opencodex/blob/main/LICENSE).
