#!/usr/bin/env python3
"""Validate the package offline using pinned portable schemas and shared invariants."""
import json
import re
from pathlib import Path

import jsonschema
import yaml
from set_version import checked_version

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads((ROOT / path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate():
    portable = read_json('plugin.json')
    checked_version(portable.get('version'))
    mcp = read_json('mcp.json')
    for name, document in [('plugin', portable), ('mcp', mcp)]:
        schema = read_json(f'scripts/{name}.schema.json')
        jsonschema.validators.validator_for(schema).check_schema(schema)
        jsonschema.validate(document, schema)

    claude = read_json('.claude-plugin/plugin.json')
    codex = read_json('.codex-plugin/plugin.json')
    for manifest in [claude, codex]:
        for key in ['name', 'version', 'description', 'author', 'homepage', 'repository', 'license']:
            require(manifest[key] == portable[key], f'Manifest drift: {key}')
    require(codex['interface'] == portable['extensions']['com.openai']['interface'], 'Interface drift')
    require(codex['skills'] == './skills/', 'Unexpected compatibility skill path')
    require(codex['mcpServers'] == './.mcp.json', 'Unexpected compatibility MCP path')
    require(mcp['mcpServers']['viewprinter']['type'] == 'streamable-http', 'Portable transport')
    legacy_mcp = read_json('.mcp.json')['mcpServers']['viewprinter']
    require(legacy_mcp['type'] == 'http', 'Claude transport')
    require(legacy_mcp['url'] == mcp['mcpServers']['viewprinter']['url'] == 'https://viewprinter.tech/api/mcp', 'Endpoint drift')

    for name in ['posting', 'media', 'accounts']:
        text = (ROOT / 'skills' / name / 'SKILL.md').read_text()
        metadata = yaml.safe_load(text.split('---', 2)[1])
        require(metadata['name'] == name, f'Skill name: {name}')
        require(isinstance(metadata['description'], str) and metadata['description'].strip(), f'Description: {name}')

    market = read_json('.agents/plugins/marketplace.json')
    require(market['name'] == 'viewprinter', 'Marketplace name')
    require(len(market['plugins']) == 1, 'Unexpected marketplace entries')
    entry = market['plugins'][0]
    require(entry['name'] == portable['name'], 'Marketplace plugin identity')
    require(entry['source'] == {'source': 'local', 'path': './'}, 'Marketplace source must be this repository root')
    require(entry['policy'] == {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'}, 'Marketplace policy')
    require(entry['category'] == 'Productivity', 'Marketplace category')
    for key in ['composerIcon', 'logo']:
        path = ROOT / codex['interface'][key]
        require(path.is_file() and path.resolve().is_relative_to(ROOT), f'Missing asset: {key}')

    wrapper = (ROOT / 'clawhub/SKILL.md').read_text()
    require(str(yaml.safe_load(wrapper.split('---', 2)[1])['metadata']['version']) == portable['version'], 'ClawHub version drift')
    evaluations = read_json('evals/workflows.json')
    require(evaluations['version'] == portable['version'], 'Evaluation version drift')
    names = [case['name'] for case in evaluations['evals']]
    require(len(names) == len(set(names)), 'Duplicate evaluation name')
    for case in evaluations['evals']:
        require(case['input'] and case['expect'], f'Incomplete evaluation: {case["name"]}')

    for path in [ROOT / 'README.md', ROOT / 'DISTRIBUTION.md', *ROOT.glob('docs/*.md')]:
        for target in re.findall(r'\]\(([^)\s]+)\)', path.read_text()):
            if '://' in target or target.startswith('#') or target.startswith('mailto:'):
                continue
            relative = target.split('#', 1)[0]
            require((path.parent / relative).exists(), f'Broken link in {path.name}: {target}')
    print(f'Package valid: {portable["name"]} {portable["version"]}; 3 skills; {len(names)} evaluation cases (definitions only).')


if __name__ == '__main__':
    validate()
