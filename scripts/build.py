#!/usr/bin/env python3
"""Build deterministic release ZIPs and a source/checksum receipt. No publishing."""
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

from validate import ROOT, validate
from release_files import PLUGIN_FILES, SINGLE_SKILL_FILES, release_inputs, safe_path


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
    skill_zip = safe_path(ROOT, f'dist/viewprinter-social-manager-{version}.zip')
    receipt_path = safe_path(ROOT, 'dist/release.json')
    subprocess.run(['node', str(inputs['clawhub/build.mjs'])], cwd=ROOT, check=True)
    out.mkdir(exist_ok=True)
    bundle = {f'viewprinter/{name}': path.read_bytes() for name, path in inputs.items()}
    clawroot = safe_path(ROOT, 'clawhub/dist/viewprinter-social-manager')
    generated = release_inputs(clawroot, SINGLE_SKILL_FILES)
    claw = {f'viewprinter-social-manager/{name}': path.read_bytes()
            for name, path in generated.items()}
    # Every reference must survive the copy unchanged. Read from disk rather than a
    # hardcoded list: a list stops covering a reference the moment somebody adds one,
    # and the drift it exists to catch would ship unnoticed.
    references = sorted(path.stem for path in (ROOT / 'skills' / 'viewprinter' / 'references' / 'rules').glob('*.md'))
    if not references:
        raise ValueError('No references found to verify')
    for name in references:
        text = (ROOT / 'skills' / 'viewprinter' / 'references' / 'rules' / f'{name}.md').read_text()
        # Mirror clawhub/build.mjs: strip frontmatter only if there is any.
        # Rules carry none; SKILL.md does. Splitting unconditionally raises on
        # a file without it, which is why this is a match rather than a split.
        source = re.sub(r'\A---\n.*?\n---\n', '', text, count=1, flags=re.S).lstrip()
        generated = (clawroot / 'references' / 'rules' / f'{name}.md').read_text()
        if source != generated:
            raise ValueError(f'Generated reference drift: {name}')
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
    source_commit = result.stdout.strip() if result.returncode == 0 else None
    status = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True, text=True)
    receipt = {'version': version, 'sourceCommit': source_commit,
               'dirty': bool(status.stdout.strip()) if status.returncode == 0 else None,
               'artifacts': [archive(plugin_zip, bundle), archive(skill_zip, claw)]}
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    for item in receipt['artifacts']:
        print(f'{item["file"]}: {item["sha256"]}')


if __name__ == '__main__':
    build()
