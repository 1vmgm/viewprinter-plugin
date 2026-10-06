#!/usr/bin/env python3
"""Build deterministic release ZIPs and a source/checksum receipt. No publishing."""
import hashlib
import json
import subprocess
import zipfile

from validate import ROOT, validate
from release_files import (CLAWHUB_PACKAGE, PLUGIN_FILES, SINGLE_SKILL_FILES,
                           assemble_clawhub, broken_links, release_inputs, safe_path)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def archive(path, entries):
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as out:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            # Mode from the path, not from the filesystem: the build stays
            # reproducible on any checkout, and a shell script keeps the bit it
            # needs. Every file was 0644, so an extracted package shipped a
            # preflight that could not run and failed its own shape lint.
            info.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
            out.writestr(info, data)
    return {'file': path.name, 'sha256': digest(path.read_bytes()), 'bytes': path.stat().st_size,
            'files': {name: digest(data) for name, data in sorted(entries.items())}}


def build():
    # Check all declared inputs before validation or executing the bundle generator.
    inputs = release_inputs(ROOT, PLUGIN_FILES)
    safe_path(ROOT, 'clawhub/dist')
    out = safe_path(ROOT, 'dist')
    validate()
    version = json.loads((ROOT / 'plugin.json').read_text())['version']
    plugin_zip = safe_path(ROOT, f'dist/viewprinter-{version}.zip')
    skill_zip = safe_path(ROOT, f'dist/{CLAWHUB_PACKAGE}-{version}.zip')
    bare_zip = safe_path(ROOT, f'dist/viewprinter-skill-{version}.zip')
    receipt_path = safe_path(ROOT, 'dist/release.json')
    clawroot = assemble_clawhub(ROOT)
    out.mkdir(exist_ok=True)
    bundle = {f'viewprinter/{name}': path.read_bytes() for name, path in inputs.items()}
    generated = release_inputs(clawroot, SINGLE_SKILL_FILES)
    # The guides link to each other; a link that resolved in the plugin's
    # layout but not in the package's would be a dead end found mid-task.
    broken = broken_links(clawroot)
    if broken:
        raise ValueError('Broken links in the package: ' + '; '.join(broken))
    claw = {f'{CLAWHUB_PACKAGE}/{name}': path.read_bytes() for name, path in generated.items()}
    # The third artifact is the same package with SKILL.md at the archive ROOT.
    #
    # This is what `npx skills add viewprinter.tech` fetches. The well-known
    # discovery provider looks for exactly `SKILL.md` — files.get('SKILL.md') —
    # and normalizeArchivePath in the CLI sanitises paths without stripping a
    # common prefix, so the nested layout the other two zips use would simply
    # not be found. Same deterministic machinery, so the digest published in the
    # index stays stable across rebuilds.
    skill_files = {name: path.read_bytes() for name, path in generated.items()}
    if 'SKILL.md' not in skill_files:
        raise ValueError('Skill archive must carry SKILL.md at its root')
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
    source_commit = result.stdout.strip() if result.returncode == 0 else None
    status = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True, text=True)

    receipt = {'version': version, 'sourceCommit': source_commit,
               'dirty': bool(status.stdout.strip()) if status.returncode == 0 else None,
               'artifacts': [archive(plugin_zip, bundle), archive(skill_zip, claw),
                             archive(bare_zip, skill_files)]}
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    for item in receipt['artifacts']:
        print(f'{item["file"]}: {item["sha256"]}')


if __name__ == '__main__':
    build()
