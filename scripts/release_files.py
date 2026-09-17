"""Reviewed release inputs and filesystem containment checks."""
from pathlib import Path, PurePosixPath


PLUGIN_FILES = (
    'plugin.json', 'mcp.json', '.codex-plugin/plugin.json',
    '.claude-plugin/plugin.json', '.mcp.json', '.agents/plugins/marketplace.json',
    'README.md', 'DISTRIBUTION.md', 'LICENSE', 'assets/logo.png',
    'skills/accounts/SKILL.md', 'skills/media/SKILL.md', 'skills/posting/SKILL.md',
    'clawhub/build.mjs', 'clawhub/SKILL.md', 'evals/workflows.json',
    'docs/codex.md', 'docs/compatibility.md', 'docs/openclaw.md',
    'docs/troubleshooting.md', 'scripts/README.md', 'scripts/build.py',
    'scripts/validate.py', 'scripts/release_files.py', 'scripts/set_version.py',
    'scripts/test_release.py', 'scripts/requirements.txt',
    'scripts/plugin.schema.json', 'scripts/mcp.schema.json',
)

SINGLE_SKILL_FILES = (
    'SKILL.md', 'references/accounts.md', 'references/media.md',
    'references/posting.md', 'evals/evals.json',
)


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
