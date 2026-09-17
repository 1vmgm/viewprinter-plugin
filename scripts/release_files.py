"""Reviewed release inputs and filesystem containment checks."""
from pathlib import Path, PurePosixPath


PLUGIN_FILES = (
    'plugin.json', 'mcp.json', '.codex-plugin/plugin.json',
    '.claude-plugin/plugin.json', '.mcp.json', '.agents/plugins/marketplace.json',
    'README.md', 'DISTRIBUTION.md', 'LICENSE', 'assets/logo.png',
    'skills/viewprinter/SKILL.md',
    'skills/viewprinter/references/rules/amend-and-cancel.md', 'skills/viewprinter/references/rules/connecting.md',
    'skills/viewprinter/references/rules/destinations.md', 'skills/viewprinter/references/rules/drafts.md',
    'skills/viewprinter/references/rules/media-upload.md', 'skills/viewprinter/references/rules/platforms-first.md',
    'skills/viewprinter/references/rules/reading-results.md', 'skills/viewprinter/references/rules/refusals.md',
    'skills/viewprinter/references/rules/scheduling.md',
    'clawhub/build.mjs', 'clawhub/frontmatter.md', 'clawhub/SKILL.md', 'evals/workflows.json',
    'docs/codex.md', 'docs/compatibility.md', 'docs/openclaw.md',
    'docs/troubleshooting.md', 'scripts/README.md', 'scripts/build.py',
    'scripts/validate.py', 'scripts/release_files.py', 'scripts/set_version.py',
    'scripts/test_release.py', 'scripts/requirements.txt',
    'scripts/plugin.schema.json', 'scripts/mcp.schema.json', 'scripts/lint-shape.sh', 'scripts/lint-portability.sh',
    'skills/viewprinter/scripts/preflight.sh',
)

SINGLE_SKILL_FILES = (
    'SKILL.md',
    'references/rules/amend-and-cancel.md', 'references/rules/connecting.md',
    'references/rules/destinations.md', 'references/rules/drafts.md',
    'references/rules/media-upload.md', 'references/rules/platforms-first.md',
    'references/rules/reading-results.md', 'references/rules/refusals.md',
    'references/rules/scheduling.md',
    'evals/evals.json',
)


def clawhub_entry(root):
    """ClawHub's SKILL.md: its own frontmatter, the canonical skill's body.

    Mirrors clawhub/build.mjs. Defined here so the script that writes a version
    and the validator that checks one cannot disagree about the shape.
    """
    import re
    frontmatter = (root / 'clawhub' / 'frontmatter.md').read_text().rstrip('\n')
    canonical = (root / 'skills' / 'viewprinter' / 'SKILL.md').read_text()
    body = re.sub(r'\A---\n.*?\n---\n', '', canonical, count=1, flags=re.S).lstrip()
    return f'{frontmatter}\n\n{body}'


def safe_path(root, relative):
    """Reject traversal and symlinks, including in parent and output directories."""
    root = Path(root).resolve()
    name = PurePosixPath(relative)
    if name.is_absolute() or '..' in name.parts or '\\' in str(relative):
        raise ValueError(f'Path must stay inside package root: {relative}')
    path = root
    for part in name.parts:
        path /= part
        if path.is_symlink():
            raise ValueError(f'Symlink is not allowed in release path: {relative}')
    if not path.resolve().is_relative_to(root):
        raise ValueError(f'Path escapes package root: {relative}')
    return path


def release_inputs(root, names):
    inputs = {}
    for name in names:
        path = safe_path(root, name)
        if not path.is_file():
            raise ValueError(f'Missing release file: {name}')
        inputs[name] = path
    return inputs
