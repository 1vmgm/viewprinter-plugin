#!/usr/bin/env python3
"""Update every package version together, or generate a local Codex cachebuster."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import yaml

from release_files import clawhub_entry, safe_path

ROOT = Path(__file__).resolve().parents[1]
JSON_FILES = ('plugin.json', '.codex-plugin/plugin.json',
              '.claude-plugin/plugin.json', 'skills/viewprinter/evals/evals.json')
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


# Codex needs the identity keys, where to find the skills and the MCP file, and
# the interface. Every one of those already exists in the root manifest, so this
# is derived rather than authored — the block was maintained by hand in two
# files, and validate.py could only report the drift after somebody made it.
CODEX_IDENTITY = ('name', 'description', 'version', 'author', 'homepage',
                  'repository', 'license')


def codex_manifest(root):
    """Build .codex-plugin/plugin.json from the portable manifest."""
    portable = json.loads(safe_path(root, 'plugin.json').read_text())
    manifest = {key: portable[key] for key in CODEX_IDENTITY}
    manifest['skills'] = './skills/'
    # The portable file, not Claude's. The Agent Plugins schema admits stdio,
    # streamable-http and sse; Claude's type "http" does not validate against it.
    manifest['mcpServers'] = './mcp.json'
    manifest['interface'] = portable['extensions']['com.openai']['interface']
    return json.dumps(manifest, indent=2) + '\n'


# Cursor's Marketplace reads .cursor-plugin/plugin.json. Its MCP entries infer
# the transport from `url` and do not document a `type`, so the server is given
# inline as a bare URL rather than pointing at either mcp file: the portable one
# says "streamable-http" and Claude's says "http", and Cursor names neither.
CURSOR_IDENTITY = CODEX_IDENTITY + ('keywords',)


def cursor_manifest(root):
    """Build .cursor-plugin/plugin.json from the portable manifest."""
    portable = json.loads(safe_path(root, 'plugin.json').read_text())
    servers = json.loads(safe_path(root, 'mcp.json').read_text())['mcpServers']
    manifest = {'name': portable['name'],
                'displayName': portable['extensions']['com.openai']['interface']['displayName']}
    manifest.update({key: portable[key] for key in CURSOR_IDENTITY if key != 'name'})
    manifest['logo'] = 'assets/logo.png'
    manifest['skills'] = './skills/'
    manifest['mcpServers'] = {name: {'url': server['url']} for name, server in servers.items()}
    return json.dumps(manifest, indent=2) + '\n'


DERIVED = (('.codex-plugin/plugin.json', codex_manifest),
           ('.cursor-plugin/plugin.json', cursor_manifest))


def sync_codex(root):
    """Regenerate every derived manifest; True when any file changed."""
    changed = False
    for name, build in DERIVED:
        path = safe_path(root, name)
        generated = build(root)
        if not path.exists() or path.read_text() != generated:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(generated)
            changed = True
    return changed


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

    path = safe_path(root, 'clawhub/frontmatter.md')
    text = path.read_text()
    match = re.match(r'\A---\n(.*?)\n---(?:\n|$)', text, re.DOTALL)
    if not match:
        raise ValueError('Missing ClawHub frontmatter')
    document = yaml.compose(match.group(1))
    metadata = next(value for key, value in document.value if key.value == 'metadata')
    node = next(value for key, value in metadata.value if key.value == 'version')
    start = match.start(1) + node.start_mark.index
    end = match.start(1) + node.end_mark.index
    changes[path] = text[:start] + json.dumps(version) + text[end:]

    # .codex-plugin/plugin.json is derived; it is rewritten below from the
    # portable manifest once every version has been set.
    changes.pop(safe_path(root, '.codex-plugin/plugin.json'), None)

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
    sync_codex(root)
    # clawhub/entry.md is generated from the frontmatter just written plus the
    # canonical skill. Without this a version bump left the two disagreeing.
    safe_path(root, 'clawhub/entry.md').write_text(clawhub_entry(root))
    return version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version', nargs='?', help='Release version, for example 1.2.1')
    parser.add_argument('--dev', action='store_true', help='Replace build metadata with a fresh local Codex suffix')
    parser.add_argument('--sync', action='store_true', help='Regenerate the derived Codex and Cursor manifests from plugin.json and exit')
    args = parser.parse_args()
    if args.sync:
        changed = sync_codex(ROOT)
        print('Regenerated derived manifests' if changed else 'Derived manifests already match plugin.json')
        return
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
