#!/usr/bin/env python3
"""Update PKGBUILD from the latest complete, stable upstream release."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
API = "https://api.github.com/repos/lidge-jun/opencodex/releases"
PLATFORMS = {"x86_64": "x64", "aarch64": "arm64"}


def download(url, destination):
    request = Request(url, headers={"User-Agent": "opencodex-bin-updater"})
    with urlopen(request, timeout=90) as response, open(destination, "wb") as output:
        while block := response.read(1024 * 1024):
            output.write(block)


def release(suffix):
    request = Request(API + suffix, headers={"Accept": "application/vnd.github+json", "User-Agent": "opencodex-bin-updater"})
    with urlopen(request, timeout=30) as response:
        data = json.load(response)
    if data.get("draft") or data.get("prerelease"):
        raise ValueError("Latest release is not stable")
    tag = data["tag_name"]
    if not re.fullmatch(r"v[0-9]+(?:\.[0-9]+)+", tag):
        raise ValueError(f"Unexpected upstream tag: {tag}")
    return tag[1:], {asset["name"]: asset for asset in data["assets"]}


def field(contents, name):
    match = re.search(rf"(?m)^{name}=([^\n]+)$", contents)
    if not match:
        raise ValueError(f"Missing {name} in PKGBUILD")
    return match.group(1)


def replace(contents, name, value):
    updated, count = re.subn(rf"(?m)^{name}=[^\n]+$", lambda _: f"{name}={value}", contents)
    if count != 1:
        raise ValueError(f"Expected exactly one {name} in PKGBUILD")
    return updated


def check_archive(path):
    with tarfile.open(path, "r:gz") as archive:
        files = archive.getmembers()
        binaries = [member for member in files if member.isfile() and (member.name == "ocx" or member.name.endswith("/ocx"))]
        if len(binaries) != 1:
            raise ValueError(f"Expected one ocx executable in {path.name}")
        root = binaries[0].name.rsplit("/", 1)[0] + "/" if "/" in binaries[0].name else ""
        if not any(member.name.startswith(root + "gui/dist/") and member.isfile() for member in files):
            raise ValueError(f"Missing gui/dist beside ocx in {path.name}")


def asset_hash(assets, version, platform, directory):
    filename = f"ocx-{version}-bun-linux-{platform}.tar.gz"
    archive_asset = assets.get(filename)
    checksum_asset = assets.get(filename + ".sha256")
    if not archive_asset or not checksum_asset:
        raise ValueError(f"Missing archive or checksum for {platform}")
    archive = directory / filename
    checksum = directory / (filename + ".sha256")
    download(archive_asset["browser_download_url"], archive)
    download(checksum_asset["browser_download_url"], checksum)
    expected_line = checksum.read_text().strip()
    match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?([^/\s]+)", expected_line)
    if not match or match.group(2) != filename:
        raise ValueError(f"Malformed upstream checksum for {filename}: {expected_line!r}")
    with open(archive, "rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual.lower() != match.group(1).lower():
        raise ValueError(f"Checksum mismatch for {filename}")
    digest = archive_asset.get("digest")
    if digest and digest != f"sha256:{actual}":
        raise ValueError(f"GitHub asset digest mismatch for {filename}")
    check_archive(archive)
    print(f"Verified {filename}: {actual}")
    return actual


def main():
    original = (ROOT / "PKGBUILD").read_text()
    current = field(original, "pkgver")
    version, assets = release("/latest")
    comparison = int(subprocess.check_output(["vercmp", version, current], text=True).strip())
    if comparison <= 0:
        print(f"No newer stable release: current {current}, upstream {version}")
        _, current_assets = release(f"/tags/v{current}") if comparison < 0 else (version, assets)
        with tempfile.TemporaryDirectory(prefix="opencodex-check-") as temporary:
            hashes = {arch: asset_hash(current_assets, current, platform, Path(temporary)) for arch, platform in PLATFORMS.items()}
        for arch, checksum in hashes.items():
            if field(original, f"sha256sums_{arch}") != f"('{checksum}')":
                raise ValueError(f"PKGBUILD checksum mismatch for {arch}")
        return
    with tempfile.TemporaryDirectory(prefix="opencodex-update-") as temporary:
        directory = Path(temporary)
        hashes = {arch: asset_hash(assets, version, platform, directory) for arch, platform in PLATFORMS.items()}
    updated = replace(original, "pkgver", version)
    updated = replace(updated, "pkgrel", "1")
    for arch, checksum in hashes.items():
        updated = replace(updated, f"sha256sums_{arch}", f"('{checksum}')")
    (ROOT / "PKGBUILD").write_text(updated)
    try:
        metadata = subprocess.check_output(["makepkg", "--printsrcinfo"], cwd=ROOT)
    except Exception:
        (ROOT / "PKGBUILD").write_text(original)
        raise
    (ROOT / ".SRCINFO").write_bytes(metadata)
    print(f"Updated opencodex-bin to {version}-1")


if __name__ == "__main__":
    main()
