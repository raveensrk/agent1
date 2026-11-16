export const meta = {
  name: 'ishikari-build',
  description: 'Ishikari stage 2: worker ants build plans, inspector ants check, detective ants plan fixes',
  whenToUse: 'After the user approves the plans from ishikari-plan. Ends with tasks awaiting the user\'s final review.',
  phases: [
    { title: 'Build', detail: 'worker ants, max 5 at once, one worktree each' },
    { title: 'Check', detail: 'inspector and philosopher ants per built task' },
    { title: 'Fix', detail: 'detective ant plans, worker ant builds, up to 3 tries' },
    { title: 'Boards', detail: 'one board write at the end' },
  ],
}

// args: {
//   repo: string,                                   absolute repo path
//   plans: [{id, title, file, workflow?, after?}],  from ishikari-plan;
//                                                   after: ids to wait for
//   bugs?: [{task, branch, bug}],                   open bounties from ishikari-finish
// }
// Returns { tasks: [{id, branch, status, bugs, tries}] }.
// status: 'awaiting review' or 'escalated'.
//
// Speed: tasks never wait on the boards. The script keeps board rows in
// memory and one low-effort ant writes them all when the stage ends.

const MAX_WORKERS = 5
const MAX_TRIES = 3

const BUILT = {
  type: 'object',
  properties: {
    branch: { type: 'string' },
    status: { type: 'string', enum: ['built', 'stuck'] },
    notes: { type: 'string' },
  },
  required: ['branch', 'status', 'notes'],
}

const INSPECTION = {
  type: 'object',
  properties: { bugs: { type: 'array', items: { type: 'string' } } },
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

const CRITIQUES = {
  type: 'object',
  properties: { critiques: { type: 'array', items: { type: 'string' } } },
  required: ['critiques'],
}

const { repo, plans = [], bugs = [] } = args

// Board rows, keyed by their first cell. Only the script writes them.
const bulletin = {}
const bounty = {}
const critiques = []
const setRow = (board, key, cells) => { board[key] = [key, ...cells] }

// Worker limit: at most MAX_WORKERS worker ants at once, fix workers included.
let running = 0
const waiting = []
async function workerSlot(fn) {
  if (running >= MAX_WORKERS) await new Promise(r => waiting.push(r))
  running++
  try { return await fn() } finally {
    running--
    const next = waiting.shift()
    if (next) next()
  }
}

function worker(id, prompt, phase, base = 'main') {
  return workerSlot(() => agent(
    `You are a worker ant of the Ishikari workflow. You cannot ask questions:
decide on your own and go as far as you can.
Repo: ${repo}. Work in your own git worktree of that repo, never in its main
checkout: \`git -C ${repo} worktree add ${repo}/.ishikari/worktrees/${id} -B ishikari/${id}\`
(reuse the worktree if it exists, and start the branch from ${base} if it is new).
${prompt}
Commit your work on branch ishikari/${id}. Leave the worktree in place.
Return status "stuck" if you cannot finish, with what blocked you in notes.`,
    { label: `worker-ant:${id}`, phase, schema: BUILT },
  ))
}

function inspect(id, branch) {
  return agent(
    `You are the inspector ant of the Ishikari workflow. Repo: ${repo}.
Review branch ${branch} against main and its plan ${repo}/.ishikari/plans/${id}.md.
Run its tests. List real bugs only, each with how to see it. Change no files.`,
    { label: `inspector-ant:${id}`, phase: 'Check', schema: INSPECTION },
  )
}

// The philosopher critiques each built branch alongside the inspector.
function philosopher(id, branch) {
  return agent(
    `You are the philosopher ant of the Ishikari workflow. Repo: ${repo}.
Question and critique branch ${branch} against main: design, scope, missing
cases. Short, concrete questions only. Change no files.`,
    { label: `philosopher-ant:${id}`, phase: 'Check', schema: CRITIQUES },
  ).then(r => { if (r) r.critiques.forEach(c => critiques.push([id, c])) })
}

function detective(id, branch, bugList) {
  return agent(
    `You are the detective ant of the Ishikari workflow. Repo: ${repo}.
Branch ${branch} has these bugs:\n- ${bugList.join('\n- ')}
Debug and find the cause. You never write code: write a complete fix plan
for a worker ant instead. Change no files.`,
    { label: `detective-ant:${id}`, phase: 'Fix', schema: FIX_PLAN },
  )
}

async function fixLoop(id, branch, found) {
  let open = found
  for (let tries = 1; tries <= MAX_TRIES; tries++) {
    open.forEach(b => setRow(bounty, b, [id, 'fixing', String(tries)]))
    const fix = await detective(id, branch, open)
    if (!fix) continue
    const built = await worker(id, `Build this fix plan:\n${fix.plan}`, 'Fix')
    if (!built || built.status === 'stuck') continue
    const check = await inspect(id, branch)
    if (!check) continue
    found.filter(b => !check.bugs.includes(b)).forEach(b => setRow(bounty, b, [id, 'fixed', String(tries)]))
    open = check.bugs
    if (!open.length) return { bugs: [], tries }
  }
  open.forEach(b => setRow(bounty, b, [id, 'escalated', String(MAX_TRIES)]))
  return { bugs: open, tries: MAX_TRIES }
}

function finish(id, branch, result) {
  const status = result.bugs.length ? 'escalated' : 'awaiting review'
  setRow(bulletin, id, [status, result.bugs.length ? 'detective ant' : 'inspector ant'])
  return { id, branch, status, bugs: result.bugs, tries: result.tries }
}

// A plan waits for the plans in its "after" list and builds on their branch.
const doneById = {}
async function runTask(p) {
  const id = p.id
  const deps = await Promise.all((p.after || []).map(d => doneById[d]))
  const blocked = deps.find(d => !d || d.status !== 'awaiting review')
  if (deps.length && blocked) {
    setRow(bulletin, id, ['escalated', 'build script'])
    return { id, branch: `ishikari/${id}`, status: 'escalated', bugs: [`blocked: ${blocked ? blocked.id : 'a plan it needs'} did not pass`], tries: 0 }
  }
  const base = deps.length ? deps[deps.length - 1].branch : 'main'
  const job = p.workflow
    ? `Run the saved workflow "${p.workflow}" as your job, with the plan in ${p.file}.`
    : `Build the plan in ${p.file}.`
  const built = await worker(id, job, 'Build', base)
  const branch = built ? built.branch : `ishikari/${id}`
  if (!built || built.status === 'stuck') {
    const bug = `stuck: ${built ? built.notes : 'worker ant died'}`
    setRow(bounty, bug, [id, 'open', '0'])
    return finish(id, branch, await fixLoop(id, branch, [bug]))
  }
  setRow(bulletin, id, ['inspecting', 'inspector ant'])
  const [check] = await Promise.all([inspect(id, branch), philosopher(id, branch)])
  const found = check ? check.bugs : ['inspector ant died']
  if (!found.length) return finish(id, branch, { bugs: [], tries: 0 })
  found.forEach(b => setRow(bounty, b, [id, 'open', '0']))
  return finish(id, branch, await fixLoop(id, branch, found))
}

plans.forEach(p => { doneById[p.id] = new Promise(r => { p.resolve = r }) })
const tasks = await parallel([
  ...plans.map(p => async () => { const r = await runTask(p); p.resolve(r); return r }),
  // Open bounties from a broken merge re-enter the fix loop directly.
  ...bugs.map(b => async () => finish(b.task, b.branch, await fixLoop(b.task, b.branch, [b.bug]))),
])

// One board write for the whole stage.
const table = rows => rows.map(r => `| ${r.join(' | ')} |`).join('\n')
await agent(
  `Board clerk for Ishikari. Repo: ${repo}. Update these board tables in the
main checkout. Add or replace rows by their first cell, keep tables aligned,
change nothing else, and do not commit.

boards/bulletin.md (Task | Status | Ant | Time; Time is "-"):
${table(Object.values(bulletin).map(r => [...r, '-']))}

boards/bounty.md (Bug | Task | Status | Tries):
${table(Object.values(bounty)) || '(no rows)'}

boards/critiques.md (Target | Critique | Time; Time is "-"):
${table(critiques.map(r => [...r, '-'])) || '(no rows)'}`,
  { label: 'board-clerk', phase: 'Boards', effort: 'low' },
)

return { tasks: tasks.filter(Boolean) }
