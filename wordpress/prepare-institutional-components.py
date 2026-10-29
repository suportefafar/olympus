#!/usr/bin/env python3
"""Export pinned custom WordPress components outside the public content tree."""
import argparse
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile

NAMES = {'fafar-cf7crud': 'FAFAR_INSTITUTIONAL_PLUGIN_PATH',
         'institutional-astra-child-theme': 'FAFAR_INSTITUTIONAL_THEME_PATH'}

def git(cache, *args):
    return subprocess.check_output(['git', '--git-dir', str(cache), *args])

def manifest(path):
    entries = []
    for line in path.read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        name, url, revision = line.split('\t')
        if name not in NAMES or not re.fullmatch('[0-9a-f]{40}', revision) or url.startswith('-'):
            raise ValueError('Invalid institutional component pin')
        entries.append((name, url, revision))
    if len(entries) != 2 or {e[0] for e in entries} != set(NAMES):
        raise ValueError('Both institutional components must be pinned exactly once')
    return entries

def export(cache, revision, target):
    archive = git(cache, 'archive', '--format=tar', revision)
    staging = Path(tempfile.mkdtemp(prefix='.component-', dir=target.parent))
    try:
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            for member in source:
                path = PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts or member.issym() or member.islnk():
                    raise ValueError('Unsafe path in component archive')
                if any(part.startswith(('.git', '.env')) or part in ('tests', 'node_modules') for part in path.parts) or path.name == 'example.env':
                    continue
                destination = staging.joinpath(*path.parts)
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                    destination.chmod(0o755)
                elif member.isfile():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with source.extractfile(member) as incoming, destination.open('wb') as outgoing:
                        shutil.copyfileobj(incoming, outgoing)
                    destination.chmod(0o644)
                else:
                    raise ValueError('Unsupported component archive member')
        (staging / '.release.json').write_text(json.dumps({'revision': revision}))
        staging.chmod(0o755)
        os.rename(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--releases', type=Path, required=True)
    parser.add_argument('--paths-only', action='store_true')
    parser.add_argument('--no-pull', action='store_true')
    args = parser.parse_args()
    entries = manifest(args.manifest)
    os.environ.setdefault('GIT_TERMINAL_PROMPT', '0')
    for name, url, revision in entries:
        target = args.releases.resolve() / name / revision
        if not args.paths_only:
            if target.exists():
                marker = target / '.release.json'
                if not marker.is_file() or json.loads(marker.read_text()).get('revision') != revision:
                    raise ValueError('Existing component release is not recognized')
            else:
                args.cache.mkdir(parents=True, exist_ok=True, mode=0o700)
                cache = args.cache / (name + '.git')
                if not cache.exists():
                    if args.no_pull:
                        raise ValueError('Pinned component is not cached; rerun without --no-pull')
                    subprocess.run(['git', 'clone', '--bare', '--', url, str(cache)], check=True)
                if git(cache, 'remote', 'get-url', 'origin').decode().strip() != url:
                    raise ValueError('Component cache has an unexpected Git origin')
                if not args.no_pull:
                    subprocess.run(['git', '--git-dir', str(cache), 'fetch', 'origin', 'main:refs/heads/main'], check=True)
                subprocess.run(['git', '--git-dir', str(cache), 'merge-base', '--is-ancestor', revision, 'refs/heads/main'], check=True)
                target.parent.mkdir(parents=True, exist_ok=True)
                export(cache, revision, target)
        print(NAMES[name] + '=' + str(target))

if __name__ == '__main__':
    main()
