"""Reviewed release inputs, the single-skill package's shape, and containment checks.

Everything that ships is listed here, so adding a file is a reviewed decision:
validate.py fails on any file under skills/ that is missing from SKILL_FILES.
The ClawHub package and the bare skill archive are both assembled from these
lists by assemble_clawhub(), the one implementation clawhub/build.mjs runs.
"""
import posixpath
import re
import shutil
from pathlib import Path, PurePosixPath

# The plugin's skills. The first is the entry point a single-skill package opens
# on; the others ship beside it, in their own folders.
SKILLS = ('content-publishing', 'content-production', 'content-review',
          'content-learning', 'account-profiles')
ENTRY_SKILL = SKILLS[0]
CLAWHUB_PACKAGE = 'viewprinter-social-manager'

REPO_FILES = (
    'plugin.json', 'mcp.json', '.codex-plugin/plugin.json', '.cursor-plugin/plugin.json',
    '.claude-plugin/plugin.json', '.claude-plugin/marketplace.json', '.mcp.json', '.agents/plugins/marketplace.json',
    'README.md', 'DISTRIBUTION.md', 'LICENSE', 'assets/logo.png',
    'clawhub/build.mjs', 'clawhub/frontmatter.md', 'clawhub/entry.md',
    'docs/codex.md', 'docs/compatibility.md', 'docs/openclaw.md',
    'docs/troubleshooting.md', 'scripts/README.md', 'scripts/build.py',
    'scripts/validate.py', 'scripts/release_files.py', 'scripts/set_version.py',
    'scripts/test_release.py', 'scripts/requirements.txt',
    'scripts/plugin.schema.json', 'scripts/mcp.schema.json',
    'scripts/lint-shape.sh', 'scripts/lint-portability.sh',
    'scripts/lint_privacy.py', 'scripts/test_lint_privacy.py',
)

SKILL_FILES = (
    'skills/account-profiles/SKILL.md',
    'skills/account-profiles/agents/openai.yaml',
    'skills/account-profiles/evals/evals.json',
    'skills/account-profiles/references/brief.md',
    'skills/account-profiles/references/facebook.md',
    'skills/account-profiles/references/instagram.md',
    'skills/account-profiles/references/research.json',
    'skills/account-profiles/references/research.md',
    'skills/account-profiles/references/tiktok.md',
    'skills/account-profiles/references/youtube.md',
    'skills/account-profiles/scripts/build_review.py',
    'skills/account-profiles/scripts/preflight.sh',
    'skills/account-profiles/scripts/shared_identity.py',
    'skills/account-profiles/scripts/test_shared_identity.py',
    'skills/account-profiles/templates/group.json',
    'skills/content-learning/SKILL.md',
    'skills/content-learning/agents/openai.yaml',
    'skills/content-learning/evals/evals.json',
    'skills/content-learning/references/method.md',
    'skills/content-learning/references/creative-anatomy.md',
    'skills/content-learning/scripts/learn.py',
    'skills/content-learning/scripts/preflight.sh',
    'skills/content-learning/scripts/test_learn.py',
    'skills/content-production/SKILL.md',
    'skills/content-production/agents/openai.yaml',
    'skills/content-production/evals/evals.json',
    'skills/content-production/references/archive.md',
    'skills/content-production/references/audio.md',
    'skills/content-production/references/formats.md',
    'skills/content-production/references/formats/hook-demo.md',
    'skills/content-production/references/hardening.md',
    'skills/content-production/references/influencers.md',
    'skills/content-production/references/memory.md',
    'skills/content-production/references/phone-mounting.md',
    'skills/content-production/references/production.md',
    'skills/content-production/references/shelving.md',
    'skills/content-production/references/tools.md',
    'skills/content-production/scripts/archive.py',
    'skills/content-production/scripts/describe.py',
    'skills/content-production/scripts/memory.py',
    'skills/content-production/scripts/preflight.sh',
    'skills/content-production/scripts/shelf.py',
    'skills/content-production/scripts/test_archive.py',
    'skills/content-production/scripts/test_describe.py',
    'skills/content-production/scripts/test_memory.py',
    'skills/content-production/scripts/test_shelf.py',
    'skills/content-production/scripts/test_tools.py',
    'skills/content-production/scripts/tools.py',
    'skills/content-publishing/SKILL.md',
    'skills/content-publishing/agents/openai.yaml',
    'skills/content-publishing/evals/evals.json',
    'skills/content-publishing/references/rules/amend-and-cancel.md',
    'skills/content-publishing/references/rules/captions.md',
    'skills/content-publishing/references/rules/connecting.md',
    'skills/content-publishing/references/rules/destinations.md',
    'skills/content-publishing/references/rules/drafts.md',
    'skills/content-publishing/references/rules/learning.md',
    'skills/content-publishing/references/rules/media-upload.md',
    'skills/content-publishing/references/rules/platforms-first.md',
    'skills/content-publishing/references/rules/reading-results.md',
    'skills/content-publishing/references/rules/refusals.md',
    'skills/content-publishing/references/rules/scheduling.md',
    'skills/content-publishing/scripts/learn.py',
    'skills/content-publishing/scripts/preflight.sh',
    'skills/content-publishing/scripts/test_learn.py',
    'skills/content-review/SKILL.md',
    'skills/content-review/agents/openai.yaml',
    'skills/content-review/assets/review-workspace.html',
    'skills/content-review/evals/evals.json',
    'skills/content-review/references/review-ui.md',
    'skills/content-review/references/review.md',
    'skills/content-review/references/workspace.md',
    'skills/content-review/scripts/preflight.sh',
    'skills/content-review/scripts/review_delivery.py',
    'skills/content-review/scripts/review_formats.py',
    'skills/content-review/scripts/review_gallery.py',
    'skills/content-review/scripts/review_hub.py',
    'skills/content-review/scripts/review_mark.py',
    'skills/content-review/scripts/review_media.py',
    'skills/content-review/scripts/review_readiness.py',
    'skills/content-review/scripts/review_workspace.py',
    'skills/content-review/scripts/test_review_delivery.py',
    'skills/content-review/scripts/test_review_formats.py',
    'skills/content-review/scripts/test_review_gallery.py',
    'skills/content-review/scripts/test_review_hub.py',
    'skills/content-review/scripts/test_review_media.py',
    'skills/content-review/scripts/test_review_readiness.py',
    'skills/content-review/scripts/test_review_workspace.py',
)

PLUGIN_FILES = REPO_FILES + SKILL_FILES


def bundle_name(path):
    """Where a plugin file sits in the single-skill package, or None if it stays out.

    The entry skill's files sit at the package root. Every other skill keeps its
    folder, with SKILL.md renamed GUIDE.md: an installer that looks for SKILL.md
    must find exactly one skill, or it splits the package and every link between
    the guides breaks. Tests, preflights and Codex metadata stay in the plugin.
    """
    parts = PurePosixPath(path).parts
    if len(parts) < 3 or parts[0] != 'skills' or parts[1] not in SKILLS:
        return None
    skill, rest = parts[1], PurePosixPath(*parts[2:])
    if rest.name.startswith('test_') or rest.name == 'preflight.sh' or rest.parts[0] == 'agents':
        return None
    if skill == ENTRY_SKILL:
        return str(rest)
    if rest == PurePosixPath('SKILL.md'):
        return f'{skill}/GUIDE.md'
    return f'{skill}/{rest}'


SINGLE_SKILL_FILES = tuple(sorted(name for name in map(bundle_name, SKILL_FILES) if name))

LINK = re.compile(r'(\]\()([^)\s]+)(\))')


def strip_frontmatter(text):
    """Without its frontmatter, if it has any: inside the package a guide is a
    document already chosen, and a second description would conflict."""
    return re.sub(r'\A---\n.*?\n---\n', '', text, count=1, flags=re.S).lstrip()


def rewrite_links(text, source):
    """Relative links written for the plugin's layout at `source`, for the package's."""
    here = posixpath.dirname(source)
    there = posixpath.dirname(bundle_name(source) or '') or '.'

    def fix(match):
        target = match.group(2)
        if '://' in target or target.startswith(('#', 'mailto:')):
            return match.group(0)
        path, hash_mark, anchor = target.partition('#')
        mapped = bundle_name(posixpath.normpath(posixpath.join(here, path))) if path else None
        if mapped is None:
            return match.group(0)
        return f'{match.group(1)}{posixpath.relpath(mapped, there)}{hash_mark}{anchor}{match.group(3)}'

    return LINK.sub(fix, text)


def clawhub_entry(root):
    """ClawHub's SKILL.md: its own frontmatter, the entry skill's body.

    Defined once, here, so the script that writes a version, the validator that
    checks one and the package build cannot disagree about the shape.
    """
    frontmatter = (Path(root) / 'clawhub' / 'frontmatter.md').read_text().rstrip('\n')
    source = f'skills/{ENTRY_SKILL}/SKILL.md'
    body = rewrite_links(strip_frontmatter((Path(root) / source).read_text()), source)
    return f'{frontmatter}\n\n{body}'


def assemble_clawhub(root):
    """Write clawhub/entry.md and clawhub/dist/<package> from skills/ alone.

    Markdown is written without provenance comments: an HTML comment naming where
    a file came from reads to a security scanner as hidden instructions, which
    ClawHub's scanner flagged in 1.1.0.
    """
    root = Path(root)
    dist = safe_path(root, 'clawhub/dist')
    out = safe_path(root, f'clawhub/dist/{CLAWHUB_PACKAGE}')
    entry = clawhub_entry(root)
    if dist.exists():
        shutil.rmtree(dist)
    (root / 'clawhub' / 'entry.md').write_text(entry)
    for source in SKILL_FILES:
        name = bundle_name(source)
        if name is None:
            continue
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if name == 'SKILL.md':
            target.write_text(entry)
        elif source.endswith('.md'):
            target.write_text(rewrite_links(strip_frontmatter(safe_path(root, source).read_text()), source))
        else:
            shutil.copyfile(safe_path(root, source), target)
    return out


def broken_links(package_root):
    """Relative links inside a built package that do not resolve inside it."""
    package_root = Path(package_root).resolve()
    broken = []
    for path in sorted(package_root.rglob('*.md')):
        for _, target, _ in LINK.findall(path.read_text()):
            if '://' in target or target.startswith(('#', 'mailto:')):
                continue
            resolved = (path.parent / target.split('#', 1)[0]).resolve()
            if not resolved.exists() or not resolved.is_relative_to(package_root):
                broken.append(f'{path.relative_to(package_root)}: {target}')
    return broken


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


if __name__ == '__main__':
    built = assemble_clawhub(Path(__file__).resolve().parents[1])
    print(f'built {built} with {len(SINGLE_SKILL_FILES)} files')
