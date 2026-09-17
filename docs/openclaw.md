# OpenClaw

The existing ClawHub listing is `@1vmgm/viewprinter-social-manager`. It packages
one entry skill with references generated from this repository's shared skills.
Install it through your supported ClawHub client, then connect the MCP service.

The previously documented command is below. OpenClaw is not installed in the
current validation environment, so its flags have not been re-tested for this
release. Check `openclaw mcp add --help` for your installed version.

```bash
openclaw mcp add viewprinter \
  --url https://viewprinter.tech/api/mcp \
  --transport streamable-http --auth oauth \
  --oauth-scope "mcp:tools offline_access" \
  --oauth-client-metadata-url https://viewprinter.tech/.well-known/openclaw-client.json
openclaw mcp login viewprinter
```

Complete browser sign-in, then ask to list accounts. Installing the skill supplies
instructions; the separate MCP connection supplies tools.

See [troubleshooting](troubleshooting.md) and [distribution](../DISTRIBUTION.md).
