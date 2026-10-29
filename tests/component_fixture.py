from pathlib import Path
import shutil

def install_components(root, target):
    directory = target / 'wordpress'
    directory.mkdir(exist_ok=True)
    shutil.copy(root / 'wordpress/prepare-institutional-components.py', directory)
    manifest = []
    for name in ('fafar-cf7crud', 'institutional-astra-child-theme'):
        sha = 'a' * 40
        manifest.append(f'{name}\tunused-fixture-url\t{sha}\n')
        release = directory / 'releases' / name / sha
        release.mkdir(parents=True)
        (release / '.release.json').write_text('{"revision":"' + sha + '"}')
    (directory / 'institutional-components.tsv').write_text(''.join(manifest))
