#!/usr/bin/env python3
"""Validate the package offline using pinned portable schemas and shared invariants."""
import json
import os
import re
from pathlib import Path

try:
    import jsonschema
    import yaml
except ModuleNotFoundError as missing:  # pragma: no cover - environment guard
    # A contributor running the checks should be told what to install, not handed
    # a traceback. The shell lints need nothing and cover the layout; this suite
    # is the maintainer build step.
    raise SystemExit(
        f'{missing.name} is not installed.\n\n'
        '  This is the maintainer build step:\n'
        '    python3 -m venv .venv\n'
        '    .venv/bin/python -m pip install -r scripts/requirements.txt\n'
        '    .venv/bin/python scripts/validate.py\n\n'
        '  These need nothing and run anywhere:\n'
        '    ./scripts/lint-shape.sh\n'
        '    ./scripts/lint-portability.sh\n'
        '    python3 scripts/lint_privacy.py'
    ) from missing

from release_files import CLAWHUB_PACKAGE, ENTRY_SKILL, PLUGIN_FILES, SKILLS, clawhub_entry
from set_version import checked_version

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = 'https://viewprinter.tech/api/mcp'
SKIP_DIRS = {'.git', 'dist', '.venv', 'node_modules', '__pycache__', 'private'}
LINK = re.compile(r'\]\(([^)\s]+)\)')
# A skill must work installed on its own, so a helper two skills need is copied
# into both rather than imported across folders. The copies must stay identical:
# content-learning's learn.py once drifted far enough that it could not find a
# memory that content-publishing's had started.
SHARED_COPIES = (
    ('skills/content-publishing/scripts/learn.py', 'skills/content-learning/scripts/learn.py'),
    ('skills/content-publishing/scripts/test_learn.py', 'skills/content-learning/scripts/test_learn.py'),
)


def read_json(path):
    return json.loads((ROOT / path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def frontmatter(text, where):
    require(text.startswith('---\n'), f'Missing frontmatter: {where}')
    return yaml.safe_load(text.split('---', 2)[1])


def check_description(value, where):
    require(isinstance(value, str) and value.strip(), f'Description: {where}')
    # The Agent Skills limit; longer descriptions are cut where agents read them.
    require(len(value) <= 1024, f'Description longer than 1024 characters: {where}')


def check_links(path, inside):
    """Every relative link in `path` resolves to something that exists inside `inside`."""
    for target in LINK.findall(path.read_text()):
        if '://' in target or target.startswith(('#', 'mailto:')):
            continue
        relative = target.split('#', 1)[0]
        resolved = (path.parent / relative).resolve()
        where = path.relative_to(ROOT)
        require(resolved.exists(), f'Broken link in {where}: {target}')
        require(resolved.is_relative_to(inside.resolve()), f'Link leaves {inside.relative_to(ROOT) if inside != ROOT else "the package"} in {where}: {target}')


def stray_skill_files():
    """A SKILL.md anywhere but skills/<name>/ is installed as a skill by repository scanners."""
    allowed = {ROOT / 'skills' / name / 'SKILL.md' for name in SKILLS}
    found = []
    for directory, subdirectories, files in os.walk(ROOT):
        subdirectories[:] = sorted(d for d in subdirectories if d not in SKIP_DIRS)
        if 'SKILL.md' in files and Path(directory, 'SKILL.md') not in allowed:
            found.append(str(Path(directory, 'SKILL.md').relative_to(ROOT)))
    return found


def check_manifests(portable):
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
    # Derived, not authored: assert the files on disk are exactly what the
    # generator produces, so a hand-edit fails here instead of shipping.
    from set_version import DERIVED
    for name, generate in DERIVED:
        require((ROOT / name).read_text() == generate(ROOT),
                f'Run scripts/set_version.py --sync: {name} is hand-edited')
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
    require(claude.get('mcpServers') == './.mcp.json',
            "Claude manifest must declare \"mcpServers\": \"./.mcp.json\"")
    require(claude.get('mcpServers') != codex.get('mcpServers'),
            'Claude and Codex must not share one MCP file — the transports differ')
    require(mcp['mcpServers']['viewprinter']['type'] == 'streamable-http', 'Portable transport')
    legacy_mcp = read_json('.mcp.json')['mcpServers']['viewprinter']
    require(legacy_mcp['type'] == 'http', 'Claude transport')
    require(legacy_mcp['url'] == mcp['mcpServers']['viewprinter']['url'] == ENDPOINT, 'Endpoint drift')

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


def check_evaluations(name, evaluations, portable):
    """Every skill carries test prompts; ids run 1..n so a gap shows a deleted case."""
    require(evaluations['skill_name'] == name, f'evals.json skill_name must match the skill: {name}')
    ids = [case['id'] for case in evaluations['evals']]
    require(ids == list(range(1, len(ids) + 1)), f'Evaluation ids must run 1..n without gaps: {name}')
    for case in evaluations['evals']:
        require(case.get('prompt') and (case.get('assertions') or case.get('expected_output')),
                f'Incomplete evaluation: {name} {case["id"]}')
    if name == ENTRY_SKILL:
        require(evaluations['version'] == portable['version'], 'Evaluation version drift')
        names = [case['name'] for case in evaluations['evals']]
        require(len(names) == len(set(names)), 'Duplicate evaluation name')
    return len(ids)


def check_publishing_rules(evaluations):
    """Every rule is routed to from SKILL.md and covered by a case that names it.

    A rule nothing points at is never read; a route with no file is a dead end
    the agent discovers mid-task. Which rule a case covers is declared, not
    guessed: matching on names missed amend-and-cancel, whose case is called
    cancel-reports-what-could-not-be-recalled.
    """
    skill = ROOT / 'skills' / ENTRY_SKILL
    text = (skill / 'SKILL.md').read_text()
    references = sorted(path.stem for path in (skill / 'references' / 'rules').glob('*.md'))
    require(references, 'No publishing rules found')
    for name in references:
        require(f'`{name}`' in text, f'Rule not routed to from SKILL.md: {name}')
    covered = set()
    for case in evaluations['evals']:
        require(case.get('rules'), f'Evaluation declares no rules: {case["name"]}')
        for rule in case['rules']:
            require(rule in references, f'{case["name"]} names a rule that does not exist: {rule}')
            covered.add(rule)
    missing = sorted(set(references) - covered)
    require(not missing, f'No evaluation covers: {", ".join(missing)}')
    return references


def check_clawhub(portable):
    claw = frontmatter((ROOT / 'clawhub/frontmatter.md').read_text(), 'clawhub/frontmatter.md')
    require(claw.get('name') == CLAWHUB_PACKAGE, 'ClawHub name')
    check_description(claw.get('description'), 'clawhub/frontmatter.md')
    require(str(claw['metadata']['version']) == portable['version'], 'ClawHub version drift')
    require(claw.get('license') == portable['license'], 'ClawHub license drift')
    # Generated from frontmatter.md + the entry skill. Asserted here so a
    # hand-edit fails instead of shipping a second, diverging description of the
    # same product — which is what an app review caught before.
    require((ROOT / 'clawhub' / 'entry.md').read_text() == clawhub_entry(ROOT),
            'Run node clawhub/build.mjs: clawhub/entry.md is hand-edited')
    # A comment reads to a security scanner as hidden instructions.
    for name in ['clawhub/entry.md', 'clawhub/frontmatter.md']:
        require('<!--' not in (ROOT / name).read_text(), f'HTML comment in {name}')


def validate():
    portable = read_json('plugin.json')
    check_manifests(portable)

    present = sorted(path.name for path in (ROOT / 'skills').iterdir() if path.is_dir())
    require(present == sorted(SKILLS), f'Expected exactly the skills {", ".join(SKILLS)}; found {", ".join(present)}')
    cases = 0
    for name in SKILLS:
        skill = ROOT / 'skills' / name
        metadata = frontmatter((skill / 'SKILL.md').read_text(), f'skills/{name}/SKILL.md')
        require(metadata.get('name') == name, f'Skill name must match its folder: {name}')
        check_description(metadata.get('description'), f'skills/{name}')
        preflight = skill / 'scripts' / 'preflight.sh'
        require(preflight.is_file() and preflight.stat().st_mode & 0o111,
                f'Missing executable preflight: {name}')
        agent = yaml.safe_load((skill / 'agents' / 'openai.yaml').read_text())['interface']
        require(agent.get('display_name') and agent.get('short_description'), f'Agent interface: {name}')
        require(f'${name}' in agent.get('default_prompt', ''), f'Agent default prompt must name ${name}')
        evaluations = json.loads((skill / 'evals' / 'evals.json').read_text())
        cases += check_evaluations(name, evaluations, portable)
        if name == ENTRY_SKILL:
            references = check_publishing_rules(evaluations)

    check_clawhub(portable)

    for original, copy in SHARED_COPIES:
        require((ROOT / original).read_bytes() == (ROOT / copy).read_bytes(),
                f'{copy} must be an exact copy of {original}')

    stray = stray_skill_files()
    require(not stray, f'SKILL.md outside skills/<name>/ would be installed as a skill: {", ".join(stray)}')
    for path in sorted((ROOT / 'skills').rglob('*.md')):
        check_links(path, ROOT / 'skills')
    for path in [ROOT / 'README.md', ROOT / 'DISTRIBUTION.md', ROOT / 'scripts' / 'README.md',
                 *sorted(ROOT.glob('docs/*.md'))]:
        check_links(path, ROOT)

    shipped = set(PLUGIN_FILES)
    for path in sorted((ROOT / 'skills').rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.name != '.DS_Store':
            require(str(path.relative_to(ROOT)) in shipped,
                    f'Skill file missing from the release list in scripts/release_files.py: {path.relative_to(ROOT)}')
    for name in PLUGIN_FILES:
        require((ROOT / name).is_file(), f'Release list names a missing file: {name}')

    print(f'Package valid: {portable["name"]} {portable["version"]}; {len(SKILLS)} skills, '
          f'{len(references)} publishing rules; {cases} evaluation cases (definitions only).')


if __name__ == '__main__':
    validate()
