# Codex setup

The full plugin bundles three skills and the hosted MCP connection. See
[compatibility](compatibility.md) for tested versions and workflow coverage.

## Install this checkout

From the repository root:

```bash
codex plugin marketplace add .
codex plugin add viewprinter@viewprinter
```

Open a new Codex session, find ViewPrinter in the skill selector, and ask to list
your accounts. Complete browser OAuth when prompted. This local marketplace
works independently of the pending OpenAI directory review.

The GitHub installation route can be tested after these files are released.
Until then, use the checkout containing the new marketplace; the previous
revision on GitHub contains only Claude packaging.

## Update or remove

After updating the checkout to a new release, reinstall:

```bash
codex plugin add viewprinter@viewprinter
```

Start a new session. Codex uses an installed cache; editing the source directory
alone does not update that copy. For local development, generate a new cache
version across every manifest and skill bundle, then reinstall:

```bash
.venv/bin/python scripts/set_version.py --dev
.venv/bin/python scripts/validate.py
codex plugin add viewprinter@viewprinter
```

Set up the maintainer environment as described in [package checks](../scripts/README.md).
The command keeps the release version prefix and replaces the local suffix;
repeated runs do not stack suffixes. It updates root `plugin.json`, both client
manifests, ClawHub metadata, and evaluation metadata together. Changing only
the Codex compatibility manifest is insufficient because the root manifest
controls the portable package's version.

Before a public release, set the intended release version (for example,
`.venv/bin/python scripts/set_version.py 1.2.1`) and build the release archives.

Remove the plugin and, optionally, its marketplace registration:

```bash
codex plugin remove viewprinter@viewprinter
codex plugin marketplace remove viewprinter
```

Removing the local plugin does not cancel posts or disconnect social accounts
in ViewPrinter.

## Standalone skills

For a Codex surface that supports skills but not plugins, ask `$skill-installer`
to install `skills/posting`, `skills/media`, and `skills/accounts` from
`1vmgm/viewprinter-plugin` after this release is published. For local development,
Codex discovers skill folders under `~/.agents/skills/` or a project's
`.agents/skills/`.

The standalone names are `posting`, `media`, and `accounts`. Check for existing
skills with those names. The full plugin namespaces them as `viewprinter:posting`,
`viewprinter:media`, and `viewprinter:accounts`.

Add the separate tool connection for the standalone path:

```bash
codex mcp add viewprinter --url https://viewprinter.tech/api/mcp
codex mcp login viewprinter
```

Use either the plugin connection or the standalone connection to avoid duplicate
tools. Only remove an existing connection after verifying its replacement.

## Layout

- `plugin.json` and `mcp.json`: portable identity and server configuration.
- `.codex-plugin/plugin.json`: Codex compatibility manifest.
- `.agents/plugins/marketplace.json`: marketplace for the repository root package.
- `.claude-plugin/plugin.json` and `.mcp.json`: Claude compatibility.
- `skills/`: shared workflow instructions.

Portable MCP uses `type: "streamable-http"`; Claude uses `type: "http"`.
Keep the service URL identical.
