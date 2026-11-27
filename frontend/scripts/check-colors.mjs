#!/usr/bin/env node
/**
 * Fails when a color is hard-coded outside the design tokens.
 *
 * Colors belong in src/css/quasar.variables.scss only. Everywhere else use
 * Quasar color props (color="primary") or CSS variables (var(--app-surface)).
 * Checks .vue, .js and .scss files (templates, scripts and styles).
 *
 *   npm run lint:colors
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const SRC = path.join(ROOT, 'src')
const ALLOWED = new Set([path.join(SRC, 'css', 'quasar.variables.scss')])
const EXTENSIONS = new Set(['.vue', '.js', '.mjs', '.scss', '.css'])

const PATTERNS = [
  {
    name: 'hex color',
    regex: /(?<![\w&/-])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b/g,
  },
  { name: 'color function', regex: /\b(?:rgba?|hsla?)\s*\(/g },
]

function* walk(dir) {
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry)
    if (statSync(full).isDirectory()) yield* walk(full)
    else if (EXTENSIONS.has(path.extname(full))) yield full
  }
}

const problems = []
for (const file of walk(SRC)) {
  if (ALLOWED.has(file)) continue
  const lines = readFileSync(file, 'utf8').split(/\r?\n/)
  lines.forEach((line, i) => {
    for (const { name, regex } of PATTERNS) {
      for (const match of line.matchAll(regex)) {
        problems.push(
          `${path.relative(ROOT, file)}:${i + 1}:${match.index + 1}  ${name} "${match[0]}"`,
        )
      }
    }
  })
}

if (problems.length) {
  console.error(problems.join('\n'))
  console.error(
    `\n✖ ${problems.length} hard-coded color(s). Add a token to src/css/quasar.variables.scss ` +
      'and use color="..." or var(--app-...) instead.',
  )
  process.exit(1)
}
console.log('✔ no hard-coded colors outside src/css/quasar.variables.scss')
