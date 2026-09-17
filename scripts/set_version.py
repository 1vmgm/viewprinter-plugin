#!/usr/bin/env python3
"""Update every package version together, or generate a local Codex cachebuster."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import yaml

from release_files import safe_path

ROOT = Path(__file__).resolve().parents[1]
JSON_FILES = ('plugin.json', '.codex-plugin/plugin.json',
              '.claude-plugin/plugin.json', 'evals/workflows.json')
SEMVER = re.compile(
    r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'
    r'(?:-(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)'
    r'(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*)?'
    r'(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?'
)


def checked_version(version):
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise ValueError(f'Expected a semantic version, received: {version!r}')
    return version


def set_version(root, version):
    checked_version(version)
    changes = {}
    # Parse every source before writing, so malformed input cannot partly update versions.
    for name in JSON_FILES:
        path = safe_path(root, name)
        data = json.loads(path.read_text())
        if not isinstance(data.get('version'), str):
            raise ValueError(f'Missing string version: {name}')
        data['version'] = version
        changes[path] = json.dumps(data, indent=2) + '\n'

    path = safe_path(root, 'clawhub/SKILL.md')
    text = path.read_text()
    match = re.match(r'\A---\n(.*?)\n---(?:\n|$)', text, re.DOTALL)
    if not match:
        raise ValueError('Missing ClawHub skill frontmatter')
    document = yaml.compose(match.group(1))
    metadata = next(value for key, value in document.value if key.value == 'metadata')
    node = next(value for key, value in metadata.value if key.value == 'version')
    start = match.start(1) + node.start_mark.index
    end = match.start(1) + node.end_mark.index
    changes[path] = text[:start] + json.dumps(version) + text[end:]

    originals = {path: path.read_bytes() for path in changes}
    written = []
    try:
        for path, updated in changes.items():
            written.append(path)
            path.write_text(updated)
    except OSError:
        for path in written:
            path.write_bytes(originals[path])
        raise
    return version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version', nargs='?', help='Release version, for example 1.2.1')
    parser.add_argument('--dev', action='store_true', help='Replace build metadata with a fresh local Codex suffix')
    args = parser.parse_args()
    if bool(args.version) == args.dev:
        parser.error('Provide a version or --dev, but not both')
    version = args.version
    if args.dev:
        current = json.loads(safe_path(ROOT, 'plugin.json').read_text())['version']
        base = checked_version(current).split('+', 1)[0]
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        version = f'{base}+codex.{stamp}'
    print(f'Updated all package versions to {set_version(ROOT, version)}')


if __name__ == '__main__':
    main()
