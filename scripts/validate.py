#!/usr/bin/env python3
"""Validate the package offline using pinned portable schemas and shared invariants."""
import json
import re
from pathlib import Path

try:
    import jsonschema
    import yaml
except ModuleNotFoundError as missing:  # pragma: no cover - environment guard
    # A contributor running the checks should be told what to install, not handed
    # a traceback. The two shell lints below need nothing and cover the layout;
    # this suite is the maintainer build step.
    raise SystemExit(
        f'{missing.name} is not installed.\n\n'
        '  This is the maintainer build step:\n'
        '    python3 -m venv .venv\n'
        '    .venv/bin/python -m pip install -r scripts/requirements.txt\n'
        '    .venv/bin/python scripts/validate.py\n\n'
        '  These two need nothing and run anywhere:\n'
        '    ./scripts/lint-shape.sh\n'
        '    ./scripts/lint-portability.sh'
    ) from missing

from release_files import clawhub_entry
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
    # Derived, not authored: assert the file on disk is exactly what the
    # generator produces, so a hand-edit fails here instead of shipping.
    from set_version import codex_manifest
    require((ROOT / '.codex-plugin' / 'plugin.json').read_text() == codex_manifest(ROOT),
            'Run scripts/set_version.py --sync: .codex-plugin/plugin.json is hand-edited')
    require(codex['interface'] == portable['extensions']['com.openai']['interface'], 'Interface drift')
    require(codex['skills'] == './skills/', 'Unexpected compatibility skill path')
    # Each ecosystem gets its own transport, so they point at different files on
    # purpose. The portable schema admits stdio, streamable-http and sse only —
    # Claude's type "http" does not validate against it, so pointing Codex at
    # .mcp.json shipped a config its own standard rejects.
    require(codex['mcpServers'] == './mcp.json', 'Codex must use the portable mcp.json')
    # Declared, not inferred. Claude Code auto-detects a root .mcp.json only as a
    # fallback where no manifest names one, and we do have a manifest — relying on
    # the fallback is a silent break waiting for a release that tightens it.
    # .get, not []: a missing key must reach require() and print why, rather
    # than raising a KeyError that says nothing about what to add or where.
    require(claude.get('mcpServers') == './.mcp.json',
            "Claude manifest must declare \"mcpServers\": \"./.mcp.json\"")
    require(claude.get('mcpServers') != codex.get('mcpServers'),
            'Claude and Codex must not share one MCP file — the transports differ')
    require(mcp['mcpServers']['viewprinter']['type'] == 'streamable-http', 'Portable transport')
    legacy_mcp = read_json('.mcp.json')['mcpServers']['viewprinter']
    require(legacy_mcp['type'] == 'http', 'Claude transport')
    require(legacy_mcp['url'] == mcp['mcpServers']['viewprinter']['url'] == 'https://viewprinter.tech/api/mcp', 'Endpoint drift')

    # One skill, with its rules beside it. It was three top-level skills until
    # the platform rules — which govern what you may upload as much as what you
    # may post — had to live in one of them and were missing from the others.
    skills = sorted(path for path in (ROOT / 'skills').iterdir() if path.is_dir())
    require(len(skills) == 1, f'Expected one skill, found {len(skills)}')
    skill = skills[0]
    text = (skill / 'SKILL.md').read_text()
    metadata = yaml.safe_load(text.split('---', 2)[1])
    require(metadata['name'] == skill.name, f'Skill name: {skill.name}')
    require(isinstance(metadata['description'], str) and metadata['description'].strip(), f'Description: {skill.name}')

    # Every rule is routed to from SKILL.md and every route resolves. A rule
    # nothing points at is never read; a route with no file is a dead end the
    # agent discovers mid-task.
    references = sorted(path.stem for path in (skill / 'references' / 'rules').glob('*.md'))
    require(references, 'No references found')
    for name in references:
        require(f'`{name}`' in text, f'Reference not routed to from SKILL.md: {name}')

    preflight = skill / 'scripts' / 'preflight.sh'
    require(preflight.is_file(), 'Skill is missing scripts/preflight.sh')
    require(preflight.stat().st_mode & 0o111, 'scripts/preflight.sh is not executable')

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

    # Generated by clawhub/build.mjs from frontmatter.md + the canonical skill.
    # Asserted here so a hand-edit fails instead of shipping a second, diverging
    # description of the same product — which is what an app review caught before.
    require((ROOT / 'clawhub' / 'entry.md').read_text() == clawhub_entry(ROOT),
            'Run node clawhub/build.mjs: clawhub/entry.md is hand-edited')

    wrapper = (ROOT / 'clawhub/entry.md').read_text()
    require(str(yaml.safe_load(wrapper.split('---', 2)[1])['metadata']['version']) == portable['version'], 'ClawHub version drift')
    # One definition, at the location Anthropic's runner, our own lint-shape.sh
    # and ClawHub's package format all expect. build.mjs copies it into the
    # package; nothing else holds a second copy.
    evaluations = read_json('skills/viewprinter/evals/evals.json')
    require(evaluations['skill_name'] == skill.name, 'evals.json skill_name must match the skill')
    require(evaluations['version'] == portable['version'], 'Evaluation version drift')
    names = [case['name'] for case in evaluations['evals']]
    require(len(names) == len(set(names)), 'Duplicate evaluation name')
    ids = [case['id'] for case in evaluations['evals']]
    require(ids == list(range(1, len(ids) + 1)), 'Evaluation ids must run 1..n without gaps')
    for case in evaluations['evals']:
        require(case['prompt'] and case['assertions'],
                f'Incomplete evaluation: {case["name"]}')
    # Which rule a case covers is declared, not guessed. Matching on the name
    # missed amend-and-cancel, whose case is called
    # cancel-reports-what-could-not-be-recalled — a heuristic that silently
    # passes the wrong thing is worse than no check.
    covered = set()
    for case in evaluations['evals']:
        require(case.get('rules'), f'Evaluation declares no rules: {case["name"]}')
        for rule in case['rules']:
            require(rule in references, f'{case["name"]} names a rule that does not exist: {rule}')
            covered.add(rule)
    missing = sorted(set(references) - covered)
    require(not missing, f'No evaluation covers: {", ".join(missing)}')

    for path in [ROOT / 'README.md', ROOT / 'DISTRIBUTION.md', *ROOT.glob('docs/*.md')]:
        for target in re.findall(r'\]\(([^)\s]+)\)', path.read_text()):
            if '://' in target or target.startswith('#') or target.startswith('mailto:'):
                continue
            relative = target.split('#', 1)[0]
            require((path.parent / relative).exists(), f'Broken link in {path.name}: {target}')
    print(f'Package valid: {portable["name"]} {portable["version"]}; 1 skill, {len(references)} references; {len(names)} evaluation cases (definitions only).')


if __name__ == '__main__':
    validate()
