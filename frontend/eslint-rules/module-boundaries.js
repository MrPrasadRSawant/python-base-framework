/**
 * ESLint rule: keep feature modules (src/module/<name>/) independent.
 *
 *  - Code outside a module may import it only through its public entry:
 *        import { useAuthStore } from '@/module/auth'           ok
 *        import { useAuthStore } from '@/module/auth/store.js'  error
 *  - A module may not reach into another module's files, by alias or by
 *    relative path (`../users/api.js`). Inside its own folder anything goes.
 */
import path from 'node:path'

const SRC = `${path.sep}src${path.sep}`

/** Name of the module a file belongs to, or null (shell code, the registry). */
function moduleOf(absPath) {
  const normalized = path.normalize(absPath)
  const idx = normalized.lastIndexOf(`${SRC}module${path.sep}`)
  if (idx === -1) return null
  const rest = normalized.slice(idx + SRC.length + 'module'.length + 1).split(path.sep)
  return rest.length >= 2 ? rest[0] : null
}

function resolveTarget(source, filename) {
  if (source.startsWith('@/')) {
    const srcRoot = filename.slice(0, filename.lastIndexOf(SRC) + SRC.length)
    return path.join(srcRoot, source.slice(2))
  }
  if (source.startsWith('.')) return path.resolve(path.dirname(filename), source)
  return null // package import
}

function targetModule(source, absTarget) {
  // "@/module/auth" (folder) means its index.js
  const m = /(?:^@\/|[/\\])module[/\\]([^/\\]+)(?:[/\\](.+))?$/.exec(
    source.startsWith('@/') ? source : absTarget.split(path.sep).join('/'),
  )
  if (!m) return null
  const inner = m[2]
  return { name: m[1], deep: Boolean(inner) && !/^index(\.(js|mjs))?$/.test(inner) }
}

export default {
  meta: {
    type: 'problem',
    docs: { description: 'Import feature modules only through their public index' },
    schema: [],
    messages: {
      deep: "Import module '{{target}}' through its public entry '@/module/{{target}}', not its internal files.",
      cross:
        "Module '{{from}}' must not reach into module '{{target}}'. Use '@/module/{{target}}' (its public exports).",
    },
  },
  create(context) {
    const filename = context.filename
    if (!filename.includes(SRC)) return {}
    const own = moduleOf(filename)

    function check(node) {
      const source = node.source?.value
      if (typeof source !== 'string') return
      const abs = resolveTarget(source, filename)
      if (!abs) return
      const target = targetModule(source, abs)
      if (!target || !target.deep) return
      if (own === target.name) return // inside its own module
      context.report({
        node: node.source,
        messageId: own ? 'cross' : 'deep',
        data: { from: own, target: target.name },
      })
    }

    return {
      ImportDeclaration: check,
      ExportNamedDeclaration: check,
      ExportAllDeclaration: check,
      ImportExpression: check, // () => import('...') in routes
    }
  },
}
