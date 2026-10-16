#!/usr/bin/env python3
"""Preserve the existing Escuta checkout and private configuration during rename."""

import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

ORIGIN = "git@github.com:suportefafar/escuta.git"
LEGACY_ORIGINS = {
    "git@github.com:suportefafar/escuta-website.git",
    "https://github.com/suportefafar/escuta-website.git",
    "https://github.com/suportefafar/escuta-website",
}


def git(directory, *arguments):
    return subprocess.check_output(["git", "-C", str(directory), *arguments], text=True).strip()


def migrate(workspace, override=None):
    legacy = workspace / "escuta-website"
    target = workspace / "escuta"
    if legacy.exists() and target.exists():
        raise RuntimeError("Both Escuta checkout names exist; refusing to merge or overwrite their files.")
    checkout = legacy if legacy.exists() else target
    origin = None
    if checkout.exists():
        if checkout.is_symlink() or not (checkout / ".git").is_dir():
            raise RuntimeError("The Escuta path is not an independent Git checkout; refusing to move it.")
        origin = git(checkout, "remote", "get-url", "origin")
        if origin not in LEGACY_ORIGINS | {ORIGIN, "https://github.com/suportefafar/escuta.git"}:
            raise RuntimeError("Unexpected Escuta Git origin; refusing to migrate another repository.")
        if checkout == legacy and git(checkout, "status", "--porcelain"):
            raise RuntimeError("The legacy Escuta checkout has uncommitted changes; preserve them before deploying.")

    original = updated = None
    if override and override.exists():
        if override.is_symlink():
            raise RuntimeError("The production override is a symlink; refusing to replace it.")
        original = override.read_text()
        if re.search(r"^  escuta-website\s*:", original, re.M) and re.search(r"^  escuta\s*:", original, re.M):
            raise RuntimeError("The production override defines both Escuta services; resolve the conflict first.")
        updated = re.sub(r"^  escuta-website(?=\s*:)", "  escuta", original, flags=re.M)
        # Rewrite only checkout paths, retaining external legacy storage paths.
        updated = re.sub(r"(?<![\w/])\.\./escuta-website(?=[/\s:'\"},\]]|$)", "../escuta", updated)
        updated = re.sub(re.escape(str(legacy)) + r"(?=[/\s:'\"},\]]|$)", lambda _: str(target), updated)

    if origin in LEGACY_ORIGINS:
        git(checkout, "remote", "set-url", "origin", ORIGIN)
    if checkout == legacy and legacy.exists():
        legacy.rename(target)
        print("[INFO] Renamed the Escuta checkout, preserving env files, configuration and storage.")
    if original is not None and updated != original:
        # Keep an operator-readable backup without exposing private values.
        with tempfile.NamedTemporaryFile(dir=override.parent, prefix=".escuta-override-backup-", delete=False, mode="w") as backup:
            backup.write(original)
        with tempfile.NamedTemporaryFile(dir=override.parent, prefix=".escuta-override-", delete=False, mode="w") as replacement:
            replacement.write(updated)
        os.replace(replacement.name, override)
        print("[INFO] Updated the private Escuta Compose override; its previous contents were preserved in a private backup.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--production-override", type=Path)
    arguments = parser.parse_args()
    try:
        migrate(arguments.workspace, arguments.production_override)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"[ERROR] Escuta rename failed: {error}\n")
