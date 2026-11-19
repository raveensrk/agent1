export const meta = {
  name: 'ishikari-build',
  description: 'Ishikari stage 2: worker ants build the plans, detective ants check them and plan fixes, then the integrator ant tests all passing tasks combined',
  whenToUse: 'After ishikari-plan returns plans. Ends with task results; the main session approves passing tasks without asking.',
  phases: [
    { title: 'Build', detail: 'worker ants, at most 5 at once, one worktree each' },
    { title: 'Check', detail: 'one detective ant per built task: checks it, plans any fix' },
    { title: 'Fix', detail: 'worker builds the plan, detective re-checks and plans the next; 3 tries per bug' },
    { title: 'Combined', detail: 'integrator ant merges all passing tasks in a scratch copy and tests once' },
    { title: 'Logbook', detail: 'each ant\'s entry the moment it replies; the stage summary at the end' },
  ],
}

// args: {
//   env: { repo, state, run, main, tool, testCommand? },  from `ishikari.py setup`, plus
//                                                          testCommand from ishikari-plan
//   plans: [{ id, title, after?, workflow? }],             approved plans from ishikari-plan
//   bugs?: [{ task, branch?, bug, kind?, after?, guidance?, history? }]
//          open work from earlier rounds: failed merges, waiting tasks, a failed
//          app check. kind 'merge' means the branch must take in the current
//          main first. No branch (a failed app check): a new task <task> starts
//          from main, and the bug is its whole job.
// }
// Returns { stage: 'build', tasks, together } or { stage: 'error', reason }.
// Task status: 'awaiting review', 'escalated', 'blocked' or 'error'.
//
// Nothing here touches the repo's main checkout: every ant works in a
// worktree under the state folder, and the logbook lives there too.

const MAX_WORKERS = 5
const MAX_TRIES = 3   // tries per bug before it is escalated
const MAX_ROUNDS = 3  // fix rounds per task, so new bugs cannot loop forever
// For now every ant runs on the latest Opus at low effort. To tune one ant,
// change its entry here.
const MODEL = 'opus'
const EFFORT = { worker: 'low', detective: 'low', integrator: 'low', merger: 'low', clerk: 'low' }

const { env = {} } = args
const plans = Array.isArray(args.plans) ? args.plans.filter(p => p && typeof p === 'object') : []
const bugsIn = Array.isArray(args.bugs) ? args.bugs.filter(b => b && typeof b === 'object') : []

const bad = []
// Paths, the branch and the commands go into shell commands inside the ants'
// prompts: only safe characters are let through (ishikari.py setup checks too).
for (const k of ['repo', 'state', 'tool']) if (!/^\/[A-Za-z0-9._\/+-]+$/.test(env[k] || '')) bad.push(`env.${k} must be an absolute path of letters, digits and . _ / + -`)
if (!/^[A-Za-z0-9._-]+$/.test(env.run || '')) bad.push('env.run must be a run id')
if (!/^[A-Za-z0-9._][A-Za-z0-9._\/-]*$/.test(env.main || '')) bad.push('env.main must be a branch name')
for (const k of ['testCommand', 'checkCommand']) if (env[k] != null && (typeof env[k] !== 'string' || /[\n\r`]/.test(env[k]))) bad.push(`env.${k} must be one line with no backtick`)
if (args.plans != null && !Array.isArray(args.plans)) bad.push('plans must be a list')
if (args.bugs != null && !Array.isArray(args.bugs)) bad.push('bugs must be a list')
if (!plans.length && !bugsIn.length) bad.push('nothing to build: plans and bugs are both empty')
if (bad.length) return { stage: 'error', reason: bad.join('; ') }

const BUILT = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['built', 'stuck'] },
    notes: { type: 'string', description: 'what you did and any choice you made on your own; for stuck, what blocked you' },
    sha: { type: 'string', description: 'HEAD commit of your branch after your last commit' },
    testsPassed: { type: 'boolean', description: 'whether the tests passed on that commit; false if you did not run them' },
    testSummary: { type: 'string', description: 'the test command you ran and its result: counts and any failing tests' },
  },
  required: ['status', 'notes'],
}

const DETECTION = {
  type: 'object',
  properties: {
    fixed: {
      type: 'array',
      description: 'for a re-check: one entry per open bug id you were given',
      items: { type: 'object', properties: { id: { type: 'string' }, fixed: { type: 'boolean' } }, required: ['id', 'fixed'] },
    },
    bugs: { type: 'array', items: { type: 'string' }, description: 'real bugs in this task\'s own work, each with how to see it' },
    nits: { type: 'array', items: { type: 'string' }, description: 'style points and small doubts; never fixed in the loop' },
    baseProblems: { type: 'array', items: { type: 'string' }, description: 'problems in code that came from the branches this task is built on' },
    ownCommits: { type: 'integer', description: 'first check only: how many commits of its own the task branch holds' },
    cause: { type: 'string', description: 'if any bug is open or new: its cause' },
    plan: { type: 'string', description: 'if any bug is open or new: a complete fix plan a worker ant can build without questions' },
  },
  required: ['bugs'],
}

const COMBINE = {
  type: 'object',
  properties: {
    sha: { type: 'string', description: 'final commit of the scratch branch' },
    results: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          outcome: { type: 'string', enum: ['merged', 'conflict', 'tests failed'] },
          detail: { type: 'string' },
          with: { type: 'array', items: { type: 'string' }, description: 'ids of the tasks it clashes with' },
        },
        required: ['id', 'outcome', 'detail'],
      },
    },
  },
  required: ['sha', 'results'],
}

// ---- paths: computed here, never taken from what an ant says ----
const branchOf = id => `ishikari/${env.run}/${id}`
const treeOf = branch => `${env.state}/worktrees/${branch.replace(/\//g, '__')}`
const planOf = branch => {
  const m = branch.match(/^ishikari\/([^/]+)\/([^/]+)$/)
  return m ? `${env.state}/plans/${m[1]}/${m[2]}.md` : '(no plan file)'
}
// The specs sit beside the plan, in that run's plans folder.
const specOf = (task, name) => task.plan.startsWith('/') ? task.plan.replace(/[^/]*$/, name) : `(no ${name})`
const designOf = task => specOf(task, 'tech_spec.md')
const productOf = task => specOf(task, 'product_spec.md')
const where = `Repo: ${env.repo} (main branch: ${env.main}). Ishikari state folder: ${env.state}.
Use absolute paths only, and run git as \`git -C <path> ...\`. Never work in the
repo's main checkout, and never touch any other repo.`
const testsLower = env.testCommand ? `run the tests with \`${env.testCommand}\`` : 'run the repo\'s tests'
const tests = testsLower[0].toUpperCase() + testsLower.slice(1)

// ---- logbook entries: kept here, appended once at the end by the tool ----
const entries = []
const note = e => entries.push({ run: env.run, ...e })

// ---- worker limit: a finishing worker hands its slot straight to the next ----
let running = 0
const waiting = []
async function workerSlot(fn) {
  if (running < MAX_WORKERS) running++
  else await new Promise(r => waiting.push(r))
  try { return await fn() } finally {
    const next = waiting.shift()
    if (next) next(); else running--
  }
}

// A dead ant (null) is retried once; a second death is an error, not a bug.
async function twice(fn) {
  const first = await fn()
  return first != null ? first : fn()
}

// ---- logbook, written the moment each ant finishes ----
// Every ant call goes through ant(): when the ant replies, a logbook clerk
// queues one entry for it, and a single clerk appends the queue at once,
// without holding up the run. The stage's
// summary entries are still appended at the end.
// Never trust an ant's answer shape: a reply that does not fit counts as a dead
// ant, so it is retried once and then an error, never a silent pass.
const strings = v => v == null || (Array.isArray(v) && v.every(x => typeof x === 'string'))
const okBuilt = r => r && ['built', 'stuck'].includes(r.status) && typeof r.notes === 'string' ? r : null
const okDetect = r => r && Array.isArray(r.bugs) && strings(r.bugs) && strings(r.nits) && strings(r.baseProblems) &&
  (r.fixed == null || (Array.isArray(r.fixed) && r.fixed.every(f => f && typeof f === 'object'))) ? r : null
const okCombine = r => r && Array.isArray(r.results) &&
  r.results.every(x => x && typeof x === 'object' && typeof x.id === 'string' && strings(x.with)) ? r : null
const summarize = (kind, r) => {
  if (r == null) return 'died'
  const stillOpen = Array.isArray(r.fixed) ? r.fixed.filter(f => f && f.fixed === false).length : 0
  if (Array.isArray(r.bugs) && !r.bugs.length && stillOpen) return `${stillOpen} still open`
  if (Array.isArray(r.bugs)) return r.bugs.length ? `${r.bugs.length} bug${r.bugs.length > 1 ? 's' : ''} found` : 'passed'
  if (typeof r.status === 'string') return r.status
  if (Number.isInteger(r.score)) return `score ${r.score}`
  if (Array.isArray(r.results)) return `merged ${r.results.filter(x => x && x.outcome === 'merged').length} of ${r.results.length}`
  if (typeof r.ok === 'boolean') return r.ok ? 'fast-forwarded' : 'fast-forward refused'
  if (typeof r.moved === 'boolean') return r.moved ? 'main moved' : 'main not moved'
  return 'finished'
}
// One logbook clerk at a time: entries that arrive while it writes wait in
// a queue, and the next clerk appends them all in one go as soon as it ends.
const logQueue = []
const logLost = []  // entries no clerk managed to append
let logWriter = null
const logNow = entries => {
  logQueue.push(...entries)
  if (!logWriter) logWriter = (async () => {
    while (logQueue.length) {
      const batch = logQueue.splice(0)
      // A dead clerk is retried once; entries still lost go into the result.
      const write = () => agent(
        `You are Ishikari's logbook clerk. Run exactly this command and nothing else:
python3 ${env.tool} log append ${env.state} <<'ISHIKARI_ROWS_END'
${JSON.stringify(batch)}
ISHIKARI_ROWS_END`,
        { label: 'logbook-clerk:now', phase: 'Logbook', model: MODEL, effort: 'low' },
      ).catch(() => null)
      if ((await write()) == null && (await write()) == null) logLost.push(...batch)
    }
    logWriter = null
  })()
}
async function ant(prompt, opts) {
  // A call that throws is a dead ant: it never takes the whole stage down.
  const r = await agent(prompt, { ...opts, model: MODEL }).catch(() => null)
  const [kind, a, b] = String(opts.label).split(':')
  const task = kind === 'juror-ant' ? b : ['worker-ant', 'detective-ant'].includes(kind) && a ? a : undefined
  logNow([{ run: env.run, ...(task ? { task } : {}), who: kind.replace('-ant', ' ant'), event: summarize(kind, r),
    ...(r != null ? { detail: JSON.stringify(r).slice(0, 400) } : {}) }])
  return r
}
const logsDone = async () => { while (logWriter) await logWriter }

function work(task, job, phase, step) {
  const start = task.bases[0] || env.main
  const more = task.bases.slice(1)
  const run = () => ant(
    `You are a worker ant of the Ishikari workflow. You cannot ask questions:
decide on your own and go as far as you can.
${where}
Your worktree is ${task.tree} on branch ${task.branch}.
If that worktree exists, use it. Else, if the branch exists, run
\`git -C ${env.repo} worktree add ${task.tree} ${task.branch}\`. Else run
\`git -C ${env.repo} worktree add -b ${task.branch} ${task.tree} ${start}\`${more.length ? `, then merge ${more.join(' and ')} into it` : ''}.
Never reset, rebase or recreate an existing branch: it holds earlier work.
The task's plan is ${task.plan}: your thin slice of the two specs (files, the spec
ids you cover, interfaces, tests). The detail is in the specs: read them. The
tech spec is ${designOf(task)}: use its names and interfaces exactly. The
behaviours and invariants are in the product spec ${productOf(task)}, by id.
If the plan file does not exist, you are the only worker of this run: your task
is the whole of the two specs.
${job}
Also update the docs your change affects, inside this task.
${tests} inside your worktree before you finish. Commit all your work on
${task.branch}, even unfinished work. Return the HEAD commit of ${task.branch}
as sha, and the test result on that commit in testsPassed and testSummary.
Return status "stuck" if you cannot finish, with what blocked you in notes.`,
    { label: `worker-ant:${task.id}:${step}`, phase, effort: EFFORT.worker, schema: BUILT },
  ).then(okBuilt)
  return workerSlot(run)
}

// A plan can name a saved workflow as its job. It runs through the runtime's
// own workflow() hook, inside a worker slot; its own agents are not counted.
function runChild(task) {
  return workerSlot(async () => {
    try {
      const out = await workflow(task.workflow, {
        repo: env.repo, main: env.main, worktree: task.tree, branch: task.branch,
        base: task.bases[0] || env.main, plan: task.plan, testCommand: env.testCommand,
      })
      // A saved workflow is not trusted either: no result or an error is stuck.
      const failed = out == null || typeof out !== 'object' || out.stage === 'error'
      const r = { status: failed ? 'stuck' : 'built', notes: `workflow ${task.workflow} returned: ${String(JSON.stringify(out)).slice(0, 500)}` }
      logNow([{ run: env.run, task: task.id, who: 'worker ant', event: `workflow ${r.status}`, detail: r.notes.slice(0, 400) }])
      return r
    } catch (e) {
      const r = { status: 'stuck', notes: `workflow ${task.workflow} failed: ${e && e.message ? e.message : e}` }
      logNow([{ run: env.run, task: task.id, who: 'worker ant', event: 'workflow stuck', detail: r.notes.slice(0, 400) }])
      return r
    }
  })
}

// The worker's own test run, reused when the detective finds the same commit.
function testsFor(task, built) {
  if (!built || !/^[0-9a-f]{7,40}$/.test(built.sha || '') || typeof built.testsPassed !== 'boolean') {
    return `${tests} inside that worktree.`
  }
  return `The worker ant tested commit ${built.sha}: ${built.testsPassed ? 'passed' : 'FAILED'}. Its summary: ${built.testSummary || '(none)'}
Run \`git -C ${task.tree} rev-parse HEAD\` and \`git -C ${task.tree} status --porcelain\`.
If HEAD is ${built.sha} and the status is empty, reuse that result and do not
run the tests again. Otherwise ${testsLower} inside that worktree.`
}

// The detective ant checks a built task and, when it finds bugs, plans their fix.
// On a re-check it also says which open bugs are fixed and plans the next fix
// for the rest, with every earlier round in hand. No other ant checks or plans.
function detect(task, open, step, built) {
  const own = task.bases.length
    ? `It is built on ${task.bases.join(', ')}. Code from those branches belongs to other tasks:
list its problems in baseProblems, never in bugs. This task's own commits are
\`git -C ${env.repo} log --no-merges ${task.branch} --not ${[env.main, ...task.bases].join(' ')}\`.`
    : `This task's own changes are \`git -C ${env.repo} diff ${env.main}...${task.branch}\`.`
  const past = task.history.map(h => `Round ${h.round}:
  bugs: ${h.bugs.join('; ')}
  cause found: ${h.cause}
  fix plan: ${h.plan}
  outcome: ${h.outcome || 'unknown'}`).join('\n')
  const ask = open
    ? `Re-check these open bugs. For each id, say in "fixed" whether it is fixed now:
${open.map(b => `- ${b.id}: ${b.text}`).join('\n')}
Then list in bugs only NEW real bugs: ones the fix caused, or that break the plan.
${past ? `Earlier fix rounds:\n${past}\n` : ''}If any bug is still open or new, debug it: find the cause and write a complete fix
plan for a worker ant. Do not repeat a cause or plan that already failed: say why
it failed and try a different approach.`
    : `List real bugs: behaviour that breaks the plan, or a failing test. If there are
any, also find their cause and write a complete fix plan for a worker ant.
Count the task's own commits with \`git -C ${env.repo} rev-list --count --no-merges ${task.branch} --not ${[env.main, ...task.bases].join(' ')}\`
and return the number as ownCommits.`
  return ant(
    `You are the detective ant of the Ishikari workflow: you check the task and plan
the fix for every bug you find. You never write code yourself.
${where}
Check task "${task.id}": branch ${task.branch}, worktree ${task.tree}, plan ${task.plan}.
The plan is a thin slice of the two specs: the behaviours and invariants it covers
are written out in ${productOf(task)}. If the plan file does not exist, this is a
one-worker run and the task is the whole of the two specs.
Check it against its plan and the run's tech spec ${designOf(task)}: a name or interface
that differs from the tech spec is a bug.
${own}
${task.notes.length ? `The worker's notes: ${task.notes.join(' / ')}\n` : ''}${task.guidance ? `The user's guidance: ${task.guidance}\n` : ''}${testsFor(task, built)} Do not copy the repo anywhere else, and do not
edit tracked files.
${ask}
Put style points and small doubts in nits, not in bugs. Check that the docs
match the change.`,
    { label: `detective-ant:${task.id}:${step}`, phase: open ? 'Fix' : 'Check', effort: EFFORT.detective, schema: DETECTION },
  ).then(okDetect)
}

// Fix loop with each bug tracked by id: MAX_TRIES tries per bug, at most MAX_ROUNDS
// rounds. A round = worker builds the detective's plan, the detective re-checks
// and plans the next fix. Returns an error text if an ant died twice, else null.
// firstFix: the detective's fix plan from its first check.
async function fixLoop(task, texts, firstFix) {
  texts.forEach(t => task.addBug(t))
  let nextFix = firstFix
  for (let k = 1; k <= MAX_ROUNDS; k++) {
    const open = task.bugs.filter(b => b.open)
    if (!open.length || open.some(b => b.tries >= MAX_TRIES)) break
    open.forEach(b => { b.tries++ })
    // Round numbers run on across loops and earlier builds, so the detective's
    // memory never shows two "Round 1"s.
    const round = task.history.length + 1
    log(`${task.id}: fix round ${round} for ${open.map(b => b.id).join(', ')}`)
    const fix = nextFix && nextFix.plan ? nextFix
      : { cause: '(the detective gave no cause)', plan: `Fix these bugs:\n${open.map(b => `- ${b.id}: ${b.text}`).join('\n')}` }
    const entry = { round, bugs: open.map(b => `${b.id}: ${b.text}`), cause: fix.cause, plan: fix.plan }
    task.history.push(entry)
    const first = task.firstStep ? `${task.firstStep}\n` : ''
    task.firstStep = ''
    const built = await twice(() => work(task, `${first}Build this fix plan for ${open.map(b => b.id).join(', ')}:\n${fix.plan}`, 'Fix', `fix${round}`))
    if (!built) return 'the worker ant died twice'
    task.touched()
    task.notes.push(built.notes)
    if (built.status === 'stuck') { entry.outcome = `worker stuck: ${built.notes}`; continue }
    const check = await twice(() => detect(task, open, `recheck${round}`, built))
    if (!check) return 'the detective ant died twice'
    nextFix = check
    const done = new Set((check.fixed || []).filter(f => f.fixed).map(f => f.id))
    open.forEach(b => { if (done.has(b.id)) b.open = false })
    task.nits.push(...(check.nits || []))
    task.baseProblems.push(...(check.baseProblems || []))
    check.bugs.forEach(t => task.addBug(t))
    const left = task.bugs.filter(b => b.open)
    entry.outcome = left.length ? `still open: ${left.map(b => `${b.id}: ${b.text}`).join('; ')}` : 'fixed'
  }
  return null
}

function makeTask(id, branch, extra) {
  const task = {
    id, branch, tree: treeOf(branch), plan: planOf(branch),
    after: [], bases: [], workflow: null, firstStep: '', guidance: '',
    bugs: [], nits: [], baseProblems: [], notes: [], history: [],
    isBuilt: false, changed: false, result: null, noted: {},
    ...extra,
  }
  let n = 0
  task.addBug = text => { n++; task.bugs.push({ id: `${id}#${n}`, text, tries: 0, open: true }) }
  task.touched = () => { if (task.isBuilt) task.changed = true }
  task.builtP = new Promise(r => { task.markBuilt = ok => { task.isBuilt = true; r(ok) } })
  task.doneP = new Promise(r => { task.markDone = r })
  return task
}

function end(task, status, why) {
  const open = task.bugs.filter(b => b.open)
  // A task can end twice (a clash fix after its first end): log only what changed.
  task.bugs.forEach(b => {
    const event = `bug ${!b.open ? 'fixed' : status === 'escalated' ? 'escalated' : 'open'}`
    if (task.noted[b.id] === event) return
    task.noted[b.id] = event
    note({ task: task.id, who: 'detective ant', event, detail: `${b.id}: ${b.text}`, tries: b.tries })
  })
  const ant = { 'awaiting review': 'detective ant', escalated: 'detective ant', blocked: 'build script', error: 'build script' }[status]
  if (task.noted.status !== status) note({ task: task.id, who: ant, event: status, ...(why && why.length ? { detail: why.join('; ') } : {}) })
  task.noted.status = status
  task.result = {
    id: task.id, branch: task.branch, worktree: task.tree, plan: task.plan, status,
    after: task.after, bugs: [...why, ...open.map(b => `${b.id}: ${b.text}`)],
    tries: Math.max(0, ...task.bugs.map(b => b.tries)),
    nits: task.nits, baseProblems: task.baseProblems, notes: task.notes, history: task.history,
  }
  if (status !== 'awaiting review') log(`${task.id}: ${status}${why.length ? ` (${why.join('; ')})` : ''}`)
  task.markBuilt(false)  // no-op if already marked
  task.markDone(task.result)
  return task.result
}

// ---- tasks from the approved plans ----
const byId = {}
const tasks = []
const problems = {}
for (const p of plans) {
  const id = String(p.id || '')
  const task = makeTask(id, branchOf(id), {
    after: Array.isArray(p.after) ? p.after.map(String) : [],
    workflow: p.workflow || null,
  })
  task.bases = task.after.map(branchOf)
  if (!/^[a-z0-9][a-z0-9-]{0,40}$/.test(id)) problems[id] = `bad plan id "${id}"`
  else if (byId[id]) problems[id] = `two plans have the id "${id}"`
  else if (p.after != null && !Array.isArray(p.after)) problems[id] = `plan "${id}": after must be a list`
  else if (p.workflow != null && typeof p.workflow !== 'string') problems[id] = `plan "${id}": workflow must be a name`
  tasks.push(task)
  if (!byId[id]) byId[id] = task
}
for (const t of tasks) {
  const unknown = t.after.filter(d => !byId[d] || d === t.id)
  if (unknown.length && !problems[t.id]) problems[t.id] = `after names unknown plans: ${unknown.join(', ')}`
}
// A loop of "after" lists would wait forever: find every task in one.
const seen = {}
function visit(id, path) {
  if (seen[id] === 'done' || !byId[id]) return
  if (seen[id] === 'open') {
    const loop = [...path.slice(path.indexOf(id)), id]
    loop.forEach(c => { problems[c] = problems[c] || `loop in after: ${loop.join(' -> ')}` })
    return
  }
  seen[id] = 'open'
  byId[id].after.forEach(d => visit(d, [...path, id]))
  seen[id] = 'done'
}
tasks.forEach(t => visit(t.id, []))

// ---- tasks from open bugs: one fix loop per branch ----
const bugTasks = {}
const TASK_ID = /^[a-z0-9][a-z0-9_-]{0,40}$/
// Branch names go into git commands: only Ishikari's own shape is allowed, and
// never a scratch branch (their names start with "_").
const TASK_BRANCH = /^ishikari\/[A-Za-z0-9._-]+\/[a-z0-9][a-z0-9_-]{0,40}$/
for (const b of bugsIn) {
  const fresh = !b.branch
  const id0 = String(b.task || (fresh ? 'check-fix' : String(b.branch).split('/').pop()))
  const branch = fresh ? branchOf(id0) : String(b.branch)
  if (!bugTasks[branch]) {
    const id = id0
    if (!TASK_ID.test(id)) problems[id] = `bad task id "${id}" in bugs`
    else if (!TASK_BRANCH.test(branch)) problems[id] = `bad branch "${branch}" in bugs`
    else if (branch.split('/').pop() !== id) problems[id] = `bug task "${id}" does not match its branch "${branch}"`
    else if (Object.values(bugTasks).some(t => t.id === id)) problems[id] = `two bug tasks have the id "${id}"`
    else if (b.after != null && !Array.isArray(b.after)) problems[id] = `bug task "${id}": after must be a list`
    bugTasks[branch] = makeTask(id, branch, {
      ...(fresh ? { plan: '(none: the bug below is the whole job)' } : {}),
      after: Array.isArray(b.after) ? b.after.map(String) : [],
      // Earlier rounds, kept only in the shape the detective's memory reads.
      history: (Array.isArray(b.history) ? b.history : []).filter(h => h && typeof h === 'object' && Array.isArray(h.bugs))
        .map(h => ({ round: h.round, bugs: h.bugs.map(String), cause: String(h.cause || ''), plan: String(h.plan || ''), outcome: h.outcome ? String(h.outcome) : undefined })),
      texts: [],
    })
  }
  const t = bugTasks[branch]
  if (typeof b.bug !== 'string' || !b.bug.trim()) problems[t.id] = problems[t.id] || `bug task "${t.id}": a bug has no text`
  else t.texts.push(b.bug)
  if (b.kind === 'merge') t.firstStep = `First merge the current ${env.main} into your branch.`
  if (b.guidance) t.guidance = [t.guidance, b.guidance].filter(Boolean).join(' / ')
}
for (const t of Object.values(bugTasks)) {
  if (tasks.some(p => p.id === t.id)) problems[t.id] = `"${t.id}" is both a new plan and an open bug`
}
// A bug task built on another bug task of this round waits for it and builds on
// its branch. A base that is not in this round has landed already or is gone.
const bugById = Object.fromEntries(Object.values(bugTasks).map(t => [t.id, t]))
for (const t of Object.values(bugTasks)) {
  t.deps = t.after.filter(d => d !== t.id && bugById[d])
  t.bases = t.deps.map(d => bugById[d].branch)
}
const bugSeen = {}
const bugVisit = (id, path) => {
  if (bugSeen[id] === 'done') return
  if (bugSeen[id] === 'open') {
    const loop = [...path.slice(path.indexOf(id)), id]
    loop.forEach(c => { problems[c] = problems[c] || `loop in after: ${loop.join(' -> ')}` })
    return
  }
  bugSeen[id] = 'open'
  bugById[id].deps.forEach(d => bugVisit(d, [...path, id]))
  bugSeen[id] = 'done'
}
Object.keys(bugById).forEach(id => bugVisit(id, []))

// ---- one task, start to end ----
async function runTask(task) {
  // Start as soon as every base is built, on top of their branches.
  const built = await Promise.all(task.after.map(d => byId[d].builtP))
  const notBuilt = task.after.filter((d, k) => !built[k])
  if (notBuilt.length) return end(task, 'blocked', [`waits on ${notBuilt.join(', ')}, which did not build`])

  const first = await twice(() => task.workflow ? runChild(task) : work(task, 'Build the plan.', 'Build', 'build'))
  if (!first) return end(task, 'error', ['the worker ant died twice'])
  task.notes.push(first.notes)
  let last = first
  if (first.status === 'stuck') {
    const err = await fixLoop(task, [`stuck: ${first.notes}`])
    if (err) return end(task, 'error', [err])
    if (task.bugs.some(b => b.open)) return end(task, 'escalated', [])
    last = null  // the fix loop only re-checked the stuck bug: the full check below still runs
  }
  task.markBuilt(true)

  // Check only once every base is final. A base that failed blocks this
  // task; a base that changed after this task started is merged in first.
  const finals = await Promise.all(task.after.map(d => byId[d].doneP))
  const failed = task.after.filter((d, k) => finals[k].status !== 'awaiting review')
  if (failed.length) return end(task, 'blocked', [`built on ${failed.join(', ')}, which did not pass`])
  if (task.after.some(d => byId[d].changed)) {
    const up = await twice(() => work(task, `Merge the latest ${task.bases.join(' and ')} into your branch, keep both sides' intent, and make the tests pass.`, 'Build', 'update'))
    if (!up) return end(task, 'error', ['the worker ant died twice'])
    task.touched()
    task.notes.push(up.notes)
    last = up
    if (up.status === 'stuck') {
      const err = await fixLoop(task, [`could not take in the latest ${task.bases.join(', ')}: ${up.notes}`])
      if (err) return end(task, 'error', [err])
      if (task.bugs.some(b => b.open)) return end(task, 'escalated', [])
      last = null
    }
  }
  const err = await fullCheck(task, 'check', last)
  if (err) return end(task, 'error', [err])
  return end(task, task.bugs.some(b => b.open) ? 'escalated' : 'awaiting review', [])
}

// The full check of a task against its plan and the tech spec, then its fix loop.
// Returns an error text if an ant died twice, else null.
async function fullCheck(task, step, last) {
  const check = await twice(() => detect(task, null, step, last))
  if (!check) return 'the detective ant died twice'
  task.nits.push(...(check.nits || []))
  task.baseProblems.push(...(check.baseProblems || []))
  // "Built" needs a commit: an empty branch has built nothing.
  const found = check.ownCommits === 0 ? ['the branch holds no commit of its own: nothing was built', ...check.bugs] : check.bugs
  return found.length ? fixLoop(task, found, check) : null
}

async function runBugTask(task) {
  // Built on another bug task of this round: wait for it, then take it in.
  const finals = await Promise.all(task.deps.map(d => bugById[d].doneP))
  const failed = task.deps.filter((d, k) => finals[k].status !== 'awaiting review')
  if (failed.length) return end(task, 'blocked', [`built on ${failed.join(', ')}, which did not pass`])
  if (task.bases.length) task.firstStep = [task.firstStep, `Merge the latest ${task.bases.join(' and ')} into your branch.`].filter(Boolean).join(' ')
  task.markBuilt(true)
  const err = await fixLoop(task, task.texts)
  if (err) return end(task, 'error', [err])
  return end(task, task.bugs.some(b => b.open) ? 'escalated' : 'awaiting review', [])
}

// Never let one task's error leave others waiting forever.
async function safely(task, fn) {
  if (problems[task.id]) return end(task, 'error', [problems[task.id]])
  try { return await fn(task) } catch (e) {
    return end(task, 'error', [`error: ${e && e.message ? e.message : e}`])
  }
}

phase('Build')
await parallel([
  ...tasks.map(t => () => safely(t, runTask)),
  ...Object.values(bugTasks).map(t => () => safely(t, runBugTask)),
])
const all = [...tasks, ...Object.values(bugTasks)]

// ---- combined test: the integrator ant merges every passing task in a scratch copy, test once ----
function mergeOrder(list) {
  const ids = new Set(list.map(t => t.id))
  const out = []
  const added = new Set()
  const add = t => {
    if (added.has(t.id)) return
    added.add(t.id)
    t.after.filter(d => ids.has(d)).forEach(d => add(list.find(x => x.id === d)))
    out.push(t)
  }
  list.forEach(add)
  return out
}

function combine(list, round) {
  const branch = `ishikari/${env.run}/_together`
  const tree = treeOf(branch)
  return ant(
    `You are the integrator ant of the Ishikari workflow. You run the combined test:
a trial merge that never touches main.
${where}
Work only in a scratch worktree: ${tree} on branch ${branch}.
Start fresh: if that worktree or branch exists, remove them
(\`git -C ${env.repo} worktree remove --force ${tree}\`, \`git -C ${env.repo} branch -D ${branch}\`),
then run \`git -C ${env.repo} worktree add -b ${branch} ${tree} ${env.main}\`.
Add each task's own commits on top, in a straight line with no merge commits,
one task at a time, in this order:
${list.map(t => `- ${t.id}: ${t.branch}`).join('\n')}
For each, run \`git cherry-pick --empty=drop $(git -C ${env.repo} rev-list --reverse --no-merges --cherry-pick --right-only HEAD...<branch>)\`
inside the worktree. If it conflicts, run \`git cherry-pick --abort\`, reset the
scratch branch to where it was before this task, report "conflict" with the files
and the ids of the tasks it clashes with, and go on to the next one.
After all merges, ${testsLower} once inside ${tree}. If they fail, find
the first task whose merge makes them fail: rebuild the branch from ${env.main}
and test after each merge. Report that task as "tests failed" with the failing
tests and the tasks merged before it, leave it out, and go on until the tests pass.
Report every task. Never write or fix code yourself, and never touch ${env.main}.
Return the final commit of ${branch} as sha.`,
    { label: `integrator-ant:combined${round}`, phase: 'Combined', effort: EFFORT.integrator, schema: COMBINE },
  ).then(okCombine)
}

let together = null
for (let round = 1; round <= 2; round++) {
  const passing = mergeOrder(all.filter(t => t.result && t.result.status === 'awaiting review'))
  if (passing.length < 2) break
  phase('Combined')
  const r = await twice(() => combine(passing, round))
  if (!r) { log('combined test skipped: the integrator ant died twice'); break }
  const outcome = Object.fromEntries((Array.isArray(r.results) ? r.results : []).filter(x => x && x.id).map(x => [x.id, x]))
  const clashes = passing.filter(t => outcome[t.id] && ['conflict', 'tests failed'].includes(outcome[t.id].outcome))
  // A pass counts only when every task is reported merged and a commit is given:
  // a silent or half answer is not proof that they work together.
  const unproven = passing.filter(t => !outcome[t.id] || (outcome[t.id].outcome !== 'merged' && !clashes.includes(t)))
  if (!clashes.length && (unproven.length || !r.sha)) {
    log(`combined test not proven: ${unproven.length ? `no merge reported for ${unproven.map(t => t.id).join(', ')}` : 'no commit returned'}; finish merges and tests on its own`)
    break
  }
  if (!clashes.length) {
    together = { branch: `ishikari/${env.run}/_together`, sha: r.sha, tasks: passing.map(t => t.id) }
    break
  }
  if (round === 2) {
    clashes.forEach(t => {
      t.addBug(`does not work with the other tasks: ${outcome[t.id].detail}`)
      end(t, 'escalated', [])
    })
    break
  }
  // Round 1 clash: the task takes in the tasks it clashes with, which makes
  // them its bases, then fixes the clash in the normal fix loop.
  // One at a time, in merge order: a clash fix merges other tasks' branches, so
  // two at once could take in each other's half-done work.
  for (const t of clashes) await safely(t, async task => {
    const before = passing.slice(0, passing.indexOf(task)).map(x => x.id)
    const named = (outcome[task.id].with || []).filter(d => before.includes(d))
    const need = named.length ? named : before
    const merge = need.map(d => all.find(x => x.id === d).branch)
    need.forEach((d, k) => {
      if (!task.after.includes(d)) task.after.push(d)
      if (!task.bases.includes(merge[k])) task.bases.push(merge[k])
    })
    // The first task in the order has nothing before it to take in: its own
    // tests failed on main as it is now, so it fixes that alone.
    task.firstStep = merge.length ? `First merge ${merge.join(' and ')} into your branch, because yours clashes with them.` : `First merge the current ${env.main} into your branch.`
    const err = await fixLoop(task, [need.length ? `does not work with ${need.join(', ')}: ${outcome[task.id].detail}` : `fails on top of ${env.main}: ${outcome[task.id].detail}`])
    if (err) return end(task, 'error', [err])
    return end(task, task.bugs.some(b => b.open) ? 'escalated' : 'awaiting review', [])
  })
  // Tasks built on a clash task stand on its old tip: take the fix in and check
  // again, or block if it no longer passes. Their own dependents follow.
  const moved = new Set(clashes.filter(t => t.result.status === 'awaiting review').map(t => t.id))
  const lost = new Set(clashes.filter(t => t.result.status !== 'awaiting review').map(t => t.id))
  for (const t of passing.filter(x => !clashes.includes(x))) {
    const gone = t.after.filter(d => lost.has(d))
    if (gone.length) { lost.add(t.id); end(t, 'blocked', [`built on ${gone.join(', ')}, which did not pass`]); continue }
    if (!t.after.some(d => moved.has(d))) continue
    await safely(t, async task => {
      const up = await twice(() => work(task, `Merge the latest ${task.bases.join(' and ')} into your branch, keep both sides' intent, and make the tests pass.`, 'Fix', 'update2'))
      if (!up) return end(task, 'error', ['the worker ant died twice'])
      task.notes.push(up.notes)
      let err = up.status === 'stuck' ? await fixLoop(task, [`could not take in the latest ${task.bases.join(', ')}: ${up.notes}`]) : null
      if (!err && !task.bugs.some(b => b.open)) err = await fullCheck(task, 'check2', up.status === 'stuck' ? null : up)
      if (err) return end(task, 'error', [err])
      return end(task, task.bugs.some(b => b.open) ? 'escalated' : 'awaiting review', [])
    })
    ;(t.result.status === 'awaiting review' ? moved : lost).add(t.id)
  }
}

// ---- one logbook append for the whole stage ----
await logsDone()  // one clerk at a time: the per-reply clerk ends first
if (entries.length) {
  phase('Logbook')
  const clerk = await agent(
    `You are Ishikari's logbook clerk. Run exactly this command and nothing else:
python3 ${env.tool} log append ${env.state} <<'ISHIKARI_ROWS_END'
${JSON.stringify(entries)}
ISHIKARI_ROWS_END`,
    { label: 'logbook-clerk', phase: 'Logbook', model: MODEL, effort: EFFORT.clerk },
  ).catch(() => null)
  if (clerk == null) { logLost.push(...entries); log('logbook append skipped: the logbook clerk died; the logbook misses this stage') }
}

await logsDone()
return { stage: 'build', tasks: all.map(t => t.result), together, ...(logLost.length ? { logLost } : {}) }
