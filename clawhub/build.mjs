/**
 * Assemble the ClawHub package from this repo's skills.
 *
 * ClawHub publishes one folder with one SKILL.md at its root. skills/ now has
 * that exact shape — one skill routing to references/ — so this copies it across
 * rather than reassembling it. Rather than write the guidance twice, which is
 * how the two copies drifted the first time and how an app review found copy in
 * one surface contradicting another, clawhub/SKILL.md stays the ClawHub-facing
 * entry point and the references are copied straight across.
 *
 * skills/ stays the single source. Edit there, never in dist/.
 *
 *   node clawhub/build.mjs
 *   clawhub skill publish clawhub/dist/viewprinter-social-manager ...
 */
import { cp, mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repo = join(here, '..')
const out = join(here, 'dist', 'viewprinter-social-manager')

/** Read from disk rather than listed here. A hardcoded list silently stops
 *  shipping a reference the moment somebody adds one — the package would build
 *  clean and be missing a file nobody noticed. */
const SKILL = join(repo, 'skills', 'viewprinter')
const REFERENCES = (await readdir(join(SKILL, 'references', 'rules')))
  .filter((f) => f.endsWith('.md'))
  .map((f) => f.replace(/\.md$/, ''))
  .sort()

/**
 * ClawHub's entry point: its own frontmatter, the canonical skill's body.
 *
 * ClawHub needs frontmatter the canonical skill does not have — its package
 * name, a description written for the security scanner that names the two
 * destructive capabilities, `allowed-tools`. That part is authored, in
 * frontmatter.md. Everything below it is the skill itself, copied, so the two
 * cannot say different things about the same product.
 *
 * The body's `references/rules/…` links need no rewriting: the package mirrors
 * the source tree, so a path that resolves in skills/viewprinter also resolves
 * in the built package.
 */
async function generateEntryPoint() {
  const frontmatter = (await readFile(join(here, 'frontmatter.md'), 'utf8')).trimEnd()
  const canonical = await readFile(join(SKILL, 'SKILL.md'), 'utf8')
  const body = canonical.replace(/^---\n[\s\S]*?\n---\n/, '').trimStart()
  return `${frontmatter}\n\n${body}`
}

await rm(join(here, 'dist'), { recursive: true, force: true })
await mkdir(join(out, 'references', 'rules'), { recursive: true })

// clawhub/SKILL.md is GENERATED, not authored — see generateEntryPoint below.
// It was a hand-maintained second copy of the canonical skill, which is the exact
// drift an app review caught before. Only the frontmatter differs for ClawHub, so
// only the frontmatter is authored.
const entry = await generateEntryPoint()
await writeFile(join(here, 'SKILL.md'), entry)
await writeFile(join(out, 'SKILL.md'), entry)
await mkdir(join(out, 'evals'), { recursive: true })
await cp(join(repo, 'evals', 'workflows.json'), join(out, 'evals', 'evals.json'))

for (const name of REFERENCES) {
  const src = await readFile(join(SKILL, 'references', 'rules', `${name}.md`), 'utf8')

  // Strip frontmatter if present. References carry none — only SKILL.md does, and
  // that is Claude Code's routing metadata, a description written to decide
  // whether to LOAD the skill. Inside the package these are reference
  // documents already chosen, so frontmatter would be a second, conflicting
  // description. Kept as a safeguard in case a reference ever grows one.
  const body = src.replace(/^---\n[\s\S]*?\n---\n/, '').trimStart()

  // Written with no provenance header. An HTML comment saying where the file
  // came from reads to a security scanner as hidden instructions — ClawHub's
  // skillspector flagged exactly that in 1.1.0, at HIGH confidence, and the
  // path it mentioned (skills/<name>/SKILL.md) also made three scanners think
  // this skill reads other installed skills' files. Provenance belongs in the
  // repo, not smuggled into the artifact where only a machine reads it.
  await writeFile(join(out, 'references', 'rules', `${name}.md`), body)
}

console.log(`built ${out} with ${REFERENCES.length} references`)
