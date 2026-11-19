export const meta = {
  name: 'ishikari-plan',
  description: 'Ishikari stage 1: check the investigator ant\'s worker plans before anything is built',
  whenToUse: 'After the live investigator ant has written the product spec, the tech spec and the plans. Run again once if it had to fix the plans.',
  phases: [
    { title: 'Check', detail: 'the script checks the plan list: ids, order, shared files, paths, and that every behaviour and invariant has a worker; no ant plans here' },
  ],
}

// The live investigator ant, run by the skill, asks the user, proves the task
// can be built, and writes two specs and one plan per worker ant:
//   product_spec.md  the product's behaviours (B1, B2...) and invariants (I1, I2...)
//   tech_spec.md     the architecture and the code's shape
// Nothing is planned here: this script only checks its plan list, so two
// workers never clash, no path leaves the repo, and no behaviour or invariant
// is left without a worker.
//
// args: {
//   env: { repo, state, run, main, tool },  from `ishikari.py setup`
//   task: string,                           the task, in the user's words
//   ids: string[],                          every behaviour and invariant id in
//                                           the product spec (B1, I1...)
//   plans: [{ id, title, files, covers, after?, workflow? }],
//                                           the investigator's plan list; covers
//                                           names the spec ids the task delivers
//   testCommand: string,                    from the investigator's last reply
//   checkCommand?: string,
//   escalated?: string,                     why a fast path was given up: logged
//   recheck?: boolean,                      true on the second run, after the
//                                           investigator fixed its plans: the
//                                           'investigated' entry is not logged twice
// }
// Returns one of:
//   { stage: 'plans', productSpec, techSpec, ids, plans, testCommand, checkCommand }
//                                           each plan has file: its thin slice of
//                                           the specs, or null in a one-worker run,
//                                           where the worker builds from the specs
//   { stage: 'problems', problems, plans }  the plans need fixing: send the
//                                           problems back to the investigator once
//   { stage: 'error', reason }              bad arguments
// Nothing is committed here.

const MODEL = 'opus'  // the logbook clerk; no other ant runs in this stage

const { env = {} } = args
const task = typeof args.task === 'string' ? args.task.trim() : ''
const bad = []
// Paths, the branch and the commands go into shell commands inside the ants'
// prompts: only safe characters are let through (ishikari.py setup checks too).
for (const k of ['repo', 'state', 'tool']) if (!/^\/[A-Za-z0-9._\/+-]+$/.test(env[k] || '')) bad.push(`env.${k} must be an absolute path of letters, digits and . _ / + -`)
if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(env.run || '')) bad.push('env.run must be a run id')
if (!/^[A-Za-z0-9._][A-Za-z0-9._\/-]*$/.test(env.main || '')) bad.push('env.main must be a branch name')
for (const k of ['testCommand', 'checkCommand']) if (env[k] != null && (typeof env[k] !== 'string' || /[\n\r`]/.test(env[k]))) bad.push(`env.${k} must be one line with no backtick`)
for (const k of ['testCommand', 'checkCommand']) if (args[k] != null && (typeof args[k] !== 'string' || /[\n\r`]/.test(args[k]))) bad.push(`${k} must be one line with no backtick`)
if (!task) bad.push('task must be a non-empty text')
if (!Array.isArray(args.plans)) bad.push('plans must be the investigator\'s plan list')
if (!Array.isArray(args.ids)) bad.push('ids must be the product spec\'s behaviour and invariant ids')
if (bad.length) return { stage: 'error', reason: bad.join('; ') }

const planDir = `${env.state}/plans/${env.run}`
const productSpec = `${planDir}/product_spec.md`
const techSpec = `${planDir}/tech_spec.md`

// ---- logbook: one clerk at a time; a dead clerk is retried once ----
const logQueue = []
const logLost = []  // entries no clerk managed to append
let logWriter = null
const logNow = entries => {
  logQueue.push(...entries)
  if (!logWriter) logWriter = (async () => {
    try {
      while (logQueue.length) {
        const batch = logQueue.splice(0)
        const write = () => agent(
          `You are Ishikari's logbook clerk. Run exactly this command and nothing else:
python3 ${env.tool} log append ${env.state} <<'ISHIKARI_ROWS_END'
${JSON.stringify(batch).replaceAll('ISHIKARI_ROWS_END', 'ISHIKARI_ROWS_SAFE')}
ISHIKARI_ROWS_END`,
          { label: 'logbook-clerk:now', phase: 'Logbook', model: MODEL, effort: 'low' },
        ).catch(() => null)
        if ((await write()) == null && (await write()) == null) logLost.push(...batch)
      }
    } finally {
      logWriter = null
    }
  })()
}
const logsDone = async () => { while (logWriter) await logWriter }
const done = async result => { await logsDone(); return logLost.length ? { ...result, logLost } : result }

phase('Check')
// The live investigator runs outside any workflow, so it cannot log itself.
const escalated = typeof args.escalated === 'string' && args.escalated.trim() ? args.escalated.trim() : ''
if (args.recheck !== true) {
  logNow([{ run: env.run, who: 'investigator ant', event: 'investigated', detail: productSpec }])
  if (escalated) logNow([{ run: env.run, who: 'main session', event: 'fast path escalated', detail: escalated }])
}

// Normalise what the ant gave, so the checks below never trip on its shape:
// files become clean repo-relative paths, so "./a.py" and "a.py" are one file.
const list = v => Array.isArray(v) ? v : []
const norm = f => String(f).replace(/^\.\/+/, '').replace(/\/\.\//g, '/').replace(/\/+/g, '/').replace(/\/$/, '')
const plans = args.plans.filter(p => p && typeof p === 'object').map(p => ({
  ...p, id: String(p.id || ''), title: String(p.title || ''),
  files: [...new Set(list(p.files).map(norm))], after: list(p.after).map(String),
  covers: [...new Set(list(p.covers).map(String))],
  afterBad: p.after != null && !Array.isArray(p.after),
}))

// ---- check the plans before anyone builds them ----
const problems = []
const RESERVED = ['fast', 'check-fix']
if (plans.length !== args.plans.length) problems.push('every plan must be an object with id, title and files')
const ids = new Set()
for (const p of plans) {
  if (!/^[a-z0-9][a-z0-9-]{0,40}$/.test(p.id)) problems.push(`bad id "${p.id}": use lowercase letters, digits and dashes, at most 41 characters`)
  if (!p.files.length) problems.push(`${p.id}: lists no files`)
  const badFiles = p.files.filter(f => !f || f.startsWith('/') || f.split('/').includes('..'))
  if (badFiles.length) problems.push(`${p.id}: files must be paths inside the repo, not "${badFiles[0]}"`)
  if (p.afterBad) problems.push(`${p.id}: after must be a list`)
  if (p.workflow != null && typeof p.workflow !== 'string') problems.push(`${p.id}: workflow must be a name`)
  if (ids.has(p.id)) problems.push(`two plans have the id "${p.id}"`)
  // Ishikari's own branch names: the fast path's branch and the check-fix task.
  if (RESERVED.includes(p.id)) problems.push(`the id "${p.id}" is taken by Ishikari itself: pick another`)
  ids.add(p.id)
}
for (const p of plans) {
  for (const d of p.after) {
    if (d === p.id) problems.push(`${p.id}: after names itself`)
    else if (!ids.has(d)) problems.push(`${p.id}: after names unknown plan "${d}"`)
  }
}
const byId = new Map(plans.map(p => [p.id, p]))
const seen = new Map()
const visit = (id, path) => {
  if (seen.get(id) === 'done' || !byId.has(id)) return
  if (seen.get(id) === 'open') { problems.push(`loop in after: ${[...path.slice(path.indexOf(id)), id].join(' -> ')}`); return }
  seen.set(id, 'open')
  byId.get(id).after.forEach(d => visit(d, [...path, id]))
  seen.set(id, 'done')
}
plans.forEach(p => visit(p.id, []))
// Two tasks that edit the same file must run in order, one after the other;
// in parallel, their merge would conflict. A folder and a file inside it are
// the same ground, and so are two names that differ only by case: macOS keeps
// those as one file.
const before = id => {
  const acc = new Set()
  const walk = x => (byId.has(x) ? byId.get(x).after : []).forEach(d => { if (!acc.has(d)) { acc.add(d); walk(d) } })
  walk(id)
  return acc
}
if (!problems.length) {
  const same = (f, g) => { const x = f.toLowerCase(), y = g.toLowerCase(); return x === y || x.startsWith(`${y}/`) || y.startsWith(`${x}/`) }
  for (let a = 0; a < plans.length; a++) for (let b = a + 1; b < plans.length; b++) {
    const A = plans[a], B = plans[b]
    if (before(A.id).has(B.id) || before(B.id).has(A.id)) continue
    for (const f of A.files) {
      const g = B.files.find(x => same(f, x))
      if (g == null) continue
      problems.push(f === g ? `${A.id} and ${B.id} both edit ${f} but neither is after the other`
        : `${A.id} edits ${f} and ${B.id} edits ${g}, which overlap, but neither is after the other`)
    }
  }
}
if (!plans.length) problems.push('there are no plans')
// Every behaviour and invariant of the product spec needs a worker, and no
// plan may claim an id the spec does not have.
const SPEC_ID = /^[BI][0-9]{1,3}$/
const specIds = [...new Set(args.ids.map(String))]
const badIds = specIds.filter(x => !SPEC_ID.test(x))
if (badIds.length) problems.push(`bad spec id "${badIds[0]}": behaviours are B1, B2... and invariants I1, I2...`)
if (!specIds.length) problems.push('the product spec lists no behaviour or invariant ids')
if (specIds.length !== args.ids.length) problems.push('the product spec lists an id twice')
for (const p of plans) {
  if (!p.covers.length) problems.push(`${p.id}: covers no behaviour or invariant`)
  const unknown = p.covers.filter(x => !specIds.includes(x))
  if (unknown.length) problems.push(`${p.id}: covers "${unknown[0]}", which is not in the product spec`)
}
const orphans = specIds.filter(x => SPEC_ID.test(x) && !plans.some(p => p.covers.includes(x)))
if (orphans.length) problems.push(`no plan covers ${orphans.join(', ')}`)

logNow([{ run: env.run, who: 'plan script', event: problems.length ? 'plans refused' : `${plans.length} plan${plans.length === 1 ? '' : 's'} checked`,
  ...(problems.length ? { detail: problems.join('\n').slice(0, 400) } : {}) }])
if (problems.length) return done({ stage: 'problems', problems, plans })

return done({
  stage: 'plans',
  productSpec,
  techSpec,
  ids: specIds,
  plans: plans.map(p => ({ id: p.id, title: p.title, files: p.files, covers: p.covers, after: p.after || [], workflow: p.workflow || undefined,
    // One worker: no plan file. It builds straight from the two specs.
    file: plans.length === 1 ? null : `${planDir}/${p.id}.md` })),
  testCommand: typeof args.testCommand === 'string' ? args.testCommand : (env.testCommand || ''),
  checkCommand: typeof args.checkCommand === 'string' ? args.checkCommand : (env.checkCommand || ''),
})
