/**
 * Assemble the ClawHub package from this repo's skills.
 *
 * ClawHub publishes one folder with one SKILL.md at its root, while Claude Code
 * loads three separate skills. Rather than write the guidance twice — which is
 * how the two copies drifted the first time, and how an app review found copy in
 * one surface contradicting another — clawhub/SKILL.md is the entry point and
 * the three skills are copied in as references/ at build time.
 *
 * skills/ stays the single source. Edit there, never in dist/.
 *
 *   node clawhub/build.mjs
 *   clawhub skill publish clawhub/dist/viewprinter-social-manager ...
 */
import { cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repo = join(here, '..')
const out = join(here, 'dist', 'viewprinter-social-manager')

/** The three Claude Code skills, and what each becomes in the package. */
const REFERENCES = ['posting', 'media', 'accounts']

await rm(join(here, 'dist'), { recursive: true, force: true })
await mkdir(join(out, 'references'), { recursive: true })

await cp(join(here, 'SKILL.md'), join(out, 'SKILL.md'))
await cp(join(here, 'evals'), join(out, 'evals'), { recursive: true })

for (const name of REFERENCES) {
  const src = await readFile(join(repo, 'skills', name, 'SKILL.md'), 'utf8')

  // Strip the frontmatter. It is Claude Code's skill-routing metadata — a
  // description written to decide whether to LOAD this file. Inside the
  // package these are reference documents that have already been chosen, so
  // the frontmatter would be a second, conflicting description of the skill.
  const body = src.replace(/^---\n[\s\S]*?\n---\n/, '').trimStart()

  // Written with no provenance header. An HTML comment saying where the file
  // came from reads to a security scanner as hidden instructions — ClawHub's
  // skillspector flagged exactly that in 1.1.0, at HIGH confidence, and the
  // path it mentioned (skills/<name>/SKILL.md) also made three scanners think
  // this skill reads other installed skills' files. Provenance belongs in the
  // repo, not smuggled into the artifact where only a machine reads it.
  await writeFile(join(out, 'references', `${name}.md`), body)
}

console.log(`built ${out}`)
