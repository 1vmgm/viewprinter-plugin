#!/usr/bin/env python3
"""Build deterministic release ZIPs and a source/checksum receipt. No publishing."""
import hashlib
import json
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
            info.external_attr = 0o100644 << 16
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
    for name in ['posting', 'media', 'accounts']:
        source = (ROOT / 'skills' / name / 'SKILL.md').read_text().split('---', 2)[2].lstrip()
        generated = (clawroot / 'references' / f'{name}.md').read_text()
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
