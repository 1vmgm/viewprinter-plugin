# Package checks

Use Python 3.11+ and Node.js 20+. The plugin itself runs through the hosted MCP
service; these dependencies are for maintainers building release artifacts.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r scripts/requirements.txt
.venv/bin/python scripts/validate.py
.venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
.venv/bin/python scripts/build.py
```

The validator checks the portable manifests against pinned official schemas,
skill metadata, shared identity/versions, marketplace paths, assets, evaluation
definitions, and relative documentation links. It does not run model evaluations.

The schemas were downloaded from
`https://agent-plugins.org/schemas/1.0.0/plugin.schema.json` and
`https://agent-plugins.org/schemas/1.0.0/mcp.schema.json` on 2026-09-17.
They are stored here so validation works offline after dependencies are installed.

The build writes deterministic ZIPs to `dist/`, with a `release.json` receipt
containing source commit, dirty-tree status, and archive/file SHA-256 hashes.
The full plugin package is for local installation and release distribution.
The single-skill bundle preserves the existing ClawHub layout and can be used
when a submission surface asks for that shape. Choose the archive required by
the actual submission form; building either does not submit anything.

## Files allowed in releases

`release_files.py` explicitly lists the files included in each archive. Add a
new file to that reviewed list only when it belongs in the shipped package.
Unlisted files are excluded, including local notes, ignored files and scratch
data. Listed files must exist. Symlinks in listed paths or their parents are
rejected, as are symlinked output paths, so builds cannot read or overwrite files
outside the package through those links. The builder works without a Git checkout, including
from an extracted release archive.

## Set the version

For a release, choose its semantic version:

```bash
.venv/bin/python scripts/set_version.py 1.2.1
```

For a fresh local Codex cache version without changing the release prefix:

```bash
.venv/bin/python scripts/set_version.py --dev
```

Both commands synchronize `plugin.json`, `.codex-plugin/plugin.json`,
`.claude-plugin/plugin.json`, `clawhub/SKILL.md`, and `evals/workflows.json`.
The command validates the version and parses every source before writing.
Use an explicit release version again before publishing; do not publish a
local `+codex.` development version by accident.

The regression suite checks archive membership, symlink containment, coordinated
version updates, invalid-input behavior, and reproducible builds from extracted
archives. It performs no authentication or social publishing.
