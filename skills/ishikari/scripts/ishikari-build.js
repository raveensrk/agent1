export const meta = {
  name: 'ishikari-build',
  description: 'Ishikari stage 2: worker ants build the plans, inspector ants check them, detective ants plan fixes, then the integrator ant tests all passing tasks combined',
  whenToUse: 'After ishikari-plan returns plans. Ends with task results; the main session approves passing tasks without asking.',
  phases: [
    { title: 'Build', detail: 'worker ants, at most 5 at once, one worktree each' },
    { title: 'Check', detail: 'one inspector ant per built task' },
    { title: 'Fix', detail: 'detective plans, worker builds, inspector re-checks; 3 tries per bug' },
    { title: 'Combined', detail: 'integrator ant merges all passing tasks in a scratch copy and tests once' },
    { title: 'Logbook', detail: 'one logbook append at the end' },
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
const EFFORT = { worker: 'medium', inspector: 'medium', detective: 'high', integrator: 'medium', merger: 'medium', clerk: 'low' }

const { env = {} } = args
const plans = Array.isArray(args.plans) ? args.plans.filter(p => p && typeof p === 'object') : []
const bugsIn = Array.isArray(args.bugs) ? args.bugs.filter(b => b && typeof b === 'object') : []

const bad = []
if (!/^\//.test(env.repo || '')) bad.push('env.repo must be an absolute path')
if (!/^\//.test(env.state || '')) bad.push('env.state must be an absolute path')
if (!/^\//.test(env.tool || '')) bad.push('env.tool must be an absolute path')
if (!/^[A-Za-z0-9._-]+$/.test(env.run || '')) bad.push('env.run must be a run id like 20261117-0120')
if (!/^[A-Za-z0-9._\/-]+$/.test(env.main || '')) bad.push('env.main must be a branch name')
if (args.plans != null && !Array.isArray(args.plans)) bad.push('plans must be a list')
if (args.bugs != null && !Array.isArray(args.bugs)) bad.push('bugs must be a list')
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

const INSPECTION = {
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
    cause: { type: 'string', description: 'first check only, if there are bugs: their cause' },
    plan: { type: 'string', description: 'first check only, if there are bugs: a complete fix plan a worker ant can build without questions' },
  },
  required: ['bugs'],
}

const FIX_PLAN = {
  type: 'object',
  properties: {
    cause: { type: 'string' },
    plan: { type: 'string', description: 'complete fix plan a worker ant can build without questions' },
  },
  required: ['cause', 'plan'],
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
          outcome: { type: 'string', enum: ['merged', 'conflict', 'tests failed', 'blocked'] },
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
// The design sits beside the plan, in that run's plans folder.
const designOf = task => task.plan.startsWith('/') ? task.plan.replace(/[^/]*$/, 'architecture.md') : '(no design file)'
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

function work(task, job, phase, step) {
  const start = task.bases[0] || env.main
  const more = task.bases.slice(1)
  const run = () => agent(
    `You are a worker ant of the Ishikari workflow. You cannot ask questions:
decide on your own and go as far as you can.
${where}
Your worktree is ${task.tree} on branch ${task.branch}.
If that worktree exists, use it. Else, if the branch exists, run
\`git -C ${env.repo} worktree add ${task.tree} ${task.branch}\`. Else run
\`git -C ${env.repo} worktree add -b ${task.branch} ${task.tree} ${start}\`${more.length ? `, then merge ${more.join(' and ')} into it` : ''}.
Never reset, rebase or recreate an existing branch: it holds earlier work.
The task's plan is ${task.plan}. The run's design is ${designOf(task)}: use its
names and interfaces exactly.
${job}
Also update the docs your change affects, inside this task.
${tests} inside your worktree before you finish. Commit all your work on
${task.branch}, even unfinished work. Return the HEAD commit of ${task.branch}
as sha, and the test result on that commit in testsPassed and testSummary.
Return status "stuck" if you cannot finish, with what blocked you in notes.`,
    { label: `worker-ant:${task.id}:${step}`, phase, effort: EFFORT.worker, schema: BUILT },
  )
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
      return { status: 'built', notes: `workflow ${task.workflow} returned: ${JSON.stringify(out).slice(0, 500)}` }
    } catch (e) {
      return { status: 'stuck', notes: `workflow ${task.workflow} failed: ${e && e.message ? e.message : e}` }
    }
  })
}

// The worker's own test run, reused when the inspector finds the same commit.
function testsFor(task, built) {
  if (!built || !/^[0-9a-f]{7,40}$/.test(built.sha || '') || typeof built.testsPassed !== 'boolean') {
    return `${tests} inside that worktree.`
  }
  return `The worker ant tested commit ${built.sha}: ${built.testsPassed ? 'passed' : 'FAILED'}. Its summary: ${built.testSummary || '(none)'}
Run \`git -C ${task.tree} rev-parse HEAD\` and \`git -C ${task.tree} status --porcelain\`.
If HEAD is ${built.sha} and the status is empty, reuse that result and do not
run the tests again. Otherwise ${testsLower} inside that worktree.`
}

function inspect(task, open, step, built) {
  const own = task.bases.length
    ? `It is built on ${task.bases.join(', ')}. Code from those branches belongs to other tasks:
list its problems in baseProblems, never in bugs. This task's own commits are
\`git -C ${env.repo} log --no-merges ${task.branch} --not ${[env.main, ...task.bases].join(' ')}\`.`
    : `This task's own changes are \`git -C ${env.repo} diff ${env.main}...${task.branch}\`.`
  const ask = open
    ? `Re-check these open bugs. For each id, say in "fixed" whether it is fixed now:
${open.map(b => `- ${b.id}: ${b.text}`).join('\n')}
Then list in bugs only NEW real bugs: ones the fix caused, or that break the plan.`
    : `List real bugs: behaviour that breaks the plan, or a failing test. If there are
any, also find their cause and write a complete fix plan for a worker ant; you
never write code yourself.`
  return agent(
    `You are the inspector ant of the Ishikari workflow.
${where}
Check task "${task.id}": branch ${task.branch}, worktree ${task.tree}, plan ${task.plan}.
Check it against its plan and the run's design ${designOf(task)}: a name or interface
that differs from the design is a bug.
${own}
${testsFor(task, built)} Do not copy the repo anywhere else, and do not
edit tracked files.
${ask}
Put style points and small doubts in nits, not in bugs. Check that the docs
match the change.`,
    { label: `inspector-ant:${task.id}:${step}`, phase: open ? 'Fix' : 'Check', effort: EFFORT.inspector, schema: INSPECTION },
  )
}

function detective(task, open, history, round) {
  const past = history.map(h => `Round ${h.round}:
  bugs: ${h.bugs.join('; ')}
  cause found: ${h.cause}
  fix plan: ${h.plan}
  outcome: ${h.outcome || 'unknown'}`).join('\n')
  return agent(
    `You are the detective ant of the Ishikari workflow.
${where}
Task "${task.id}": branch ${task.branch}, worktree ${task.tree}, plan ${task.plan}.
${task.bases.length ? `It is built on ${task.bases.join(', ')}.\n` : ''}${task.notes.length ? `The worker's notes: ${task.notes.join(' / ')}\n` : ''}These bugs are open:
${open.map(b => `- ${b.id}: ${b.text}`).join('\n')}
${task.guidance ? `The user's guidance: ${task.guidance}\n` : ''}${past ? `Earlier fix rounds failed:\n${past}\nDo not repeat a cause or plan that already failed. Say why it failed and try a different approach.\n` : ''}Debug and find the cause. You never write code: write a complete fix plan for
a worker ant instead. Change no files.`,
    { label: `detective-ant:${task.id}:fix${round}`, phase: 'Fix', effort: EFFORT.detective, schema: FIX_PLAN },
  )
}

// Fix loop with each bug tracked by id: MAX_TRIES tries per bug, at most MAX_ROUNDS
// rounds. A round = detective plans, worker builds, inspector re-checks.
// Returns an error text if an ant died twice, else null.
// firstFix: the inspector's own fix plan for round 1, which saves a detective.
async function fixLoop(task, texts, firstFix) {
  texts.forEach(t => task.addBug(t))
  for (let round = 1; round <= MAX_ROUNDS; round++) {
    const open = task.bugs.filter(b => b.open)
    if (!open.length || open.some(b => b.tries >= MAX_TRIES)) break
    open.forEach(b => { b.tries++ })
    log(`${task.id}: fix round ${round} for ${open.map(b => b.id).join(', ')}`)
    const fix = round === 1 && firstFix && firstFix.plan ? firstFix : await twice(() => detective(task, open, task.history, round))
    if (!fix) return 'the detective ant died twice'
    const entry = { round, bugs: open.map(b => `${b.id}: ${b.text}`), cause: fix.cause, plan: fix.plan }
    task.history.push(entry)
    const first = task.firstStep ? `${task.firstStep}\n` : ''
    task.firstStep = ''
    const built = await twice(() => work(task, `${first}Build this fix plan for ${open.map(b => b.id).join(', ')}:\n${fix.plan}`, 'Fix', `fix${round}`))
    if (!built) return 'the worker ant died twice'
    task.touched()
    task.notes.push(built.notes)
    if (built.status === 'stuck') { entry.outcome = `worker stuck: ${built.notes}`; continue }
    const check = await twice(() => inspect(task, open, `recheck${round}`, built))
    if (!check) return 'the inspector ant died twice'
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
    isBuilt: false, changed: false, result: null,
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
  task.bugs.forEach(b => note({ task: task.id, who: 'inspector ant',
    event: `bug ${!b.open ? 'fixed' : status === 'escalated' ? 'escalated' : 'open'}`, detail: `${b.id}: ${b.text}`, tries: b.tries }))
  const ant = { 'awaiting review': 'inspector ant', escalated: 'detective ant', blocked: 'build script', error: 'build script' }[status]
  note({ task: task.id, who: ant, event: status, ...(why && why.length ? { detail: why.join('; ') } : {}) })
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
for (const b of bugsIn) {
  const fresh = !b.branch
  const id0 = String(b.task || (fresh ? 'check-fix' : String(b.branch).split('/').pop()))
  const branch = fresh ? branchOf(id0) : String(b.branch)
  if (!bugTasks[branch]) {
    const id = id0
    if (!/^[a-z0-9_][a-z0-9_-]{0,40}$/.test(id)) problems[id] = `bad task id "${id}" in bugs`
    // Branch names go into git commands: only Ishikari's own shape is allowed.
    else if (!/^ishikari\/[A-Za-z0-9._-]+\/[a-z0-9_][a-z0-9_-]{0,40}$/.test(branch)) problems[id] = `bad branch "${branch}" in bugs`
    bugTasks[branch] = makeTask(id, branch, {
      ...(fresh ? { plan: '(none: the bug below is the whole job)' } : {}),
      after: Array.isArray(b.after) ? b.after.map(String) : [],
      history: Array.isArray(b.history) ? b.history : [],
      texts: [],
    })
  }
  const t = bugTasks[branch]
  t.texts.push(String(b.bug))
  if (b.kind === 'merge') t.firstStep = `First merge the current ${env.main} into your branch.`
  if (b.guidance) t.guidance = [t.guidance, b.guidance].filter(Boolean).join(' / ')
}
for (const t of Object.values(bugTasks)) {
  if (tasks.some(p => p.id === t.id)) problems[t.id] = `"${t.id}" is both a new plan and an open bug`
}

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
  let inspected = false
  if (first.status === 'stuck') {
    const err = await fixLoop(task, [`stuck: ${first.notes}`])
    if (err) return end(task, 'error', [err])
    if (task.bugs.some(b => b.open)) return end(task, 'escalated', [])
    inspected = true
  }
  task.markBuilt(true)

  // Inspect only once every base is final. A base that failed blocks this
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
    inspected = false
    if (up.status === 'stuck') {
      const err = await fixLoop(task, [`could not take in the latest ${task.bases.join(', ')}: ${up.notes}`])
      if (err) return end(task, 'error', [err])
      inspected = true
    }
  }
  if (!inspected) {
    const check = await twice(() => inspect(task, null, 'check', last))
    if (!check) return end(task, 'error', ['the inspector ant died twice'])
    task.nits.push(...(check.nits || []))
    task.baseProblems.push(...(check.baseProblems || []))
    if (check.bugs.length) {
      const err = await fixLoop(task, check.bugs, check)
      if (err) return end(task, 'error', [err])
    }
  }
  return end(task, task.bugs.some(b => b.open) ? 'escalated' : 'awaiting review', [])
}

async function runBugTask(task) {
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
  return agent(
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
  )
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
  await parallel(clashes.map(t => () => safely(t, async task => {
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
  })))
}

// ---- one logbook append for the whole stage ----
if (entries.length) {
  phase('Logbook')
  const clerk = await agent(
    `You are Ishikari's logbook clerk. Run exactly this command and nothing else:
python3 ${env.tool} log append ${env.state} <<'ISHIKARI_ROWS_END'
${JSON.stringify(entries)}
ISHIKARI_ROWS_END`,
    { label: 'logbook-clerk', phase: 'Logbook', effort: EFFORT.clerk },
  )
  if (clerk == null) log('logbook append skipped: the logbook clerk died; the logbook misses this stage')
}

return { stage: 'build', tasks: all.map(t => t.result), together }
