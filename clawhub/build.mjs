/**
 * Assemble the ClawHub package from this repo's skills.
 *
 * ClawHub publishes one folder with one SKILL.md at its root. The package opens
 * on the content-publishing skill and carries the plugin's other skills beside
 * it as guides, so a ClawHub install gets everything the plugin has.
 *
 * The shape is defined once, in scripts/release_files.py, which this runs: the
 * version script, the validator and the build read the same definition, so they
 * cannot disagree about what ships. skills/ stays the single source — edit
 * there, never in dist/.
 *
 *   node clawhub/build.mjs
 *   clawhub skill publish clawhub/dist/viewprinter-social-manager ...
 */
import { execFileSync } from 'node:child_process'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const repo = join(dirname(fileURLToPath(import.meta.url)), '..')
execFileSync('python3', [join(repo, 'scripts', 'release_files.py')], {
  cwd: repo,
  stdio: 'inherit',
})
