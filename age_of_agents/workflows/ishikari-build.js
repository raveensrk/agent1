export const meta = {
  name: 'ishikari-build',
  description: 'Ishikari stage 2: worker ants build plans, inspector ants check, detective ants plan fixes',
  whenToUse: 'After the user approves the plans from ishikari-plan. Ends with tasks awaiting the user\'s final review.',
  phases: [
    { title: 'Build', detail: 'worker ants, max 5 at once, one worktree each' },
    { title: 'Check', detail: 'inspector ant per built task' },
    { title: 'Fix', detail: 'detective ant plans, worker ant builds, up to 3 tries' },
    { title: 'Boards', detail: 'board writes, one at a time' },
  ],
}

// args: {
//   repo: string,                                   absolute repo path
//   plans: [{id, title, file, workflow?, after?}],  from ishikari-plan;
//                                                   after: ids to wait for
//   bugs?: [{id, task, branch, bug}],               open bounties from ishikari-finish
// }
// Returns { tasks: [{id, branch, status, bugs, tries}] }.
// status: 'awaiting review' or 'escalated'.

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
  properties: {
    bugs: { type: 'array', items: { type: 'string' } },
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

const { repo, plans = [], bugs = [] } = args

// Worker limit: at most MAX_WORKERS worker ants run at once, fix workers included.
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

// Board lock: ants take turns writing a board.
let boardChain = Promise.resolve()
function post(board, row) {
  const write = () => agent(
    `Board clerk for Ishikari. In ${repo}/boards/${board}.md, add or update the
table row whose first cell is "${row[0]}" to: | ${row.join(' | ')} |
Keep the table aligned. Change nothing else.`,
    { label: `board:${board}:${row[0]}`, phase: 'Boards', effort: 'low' },
  )
  boardChain = boardChain.then(write, write)
  return boardChain
}

function worker(id, prompt, phase, base = 'main') {
  return workerSlot(() => agent(
    `You are a worker ant of the Ishikari workflow. You cannot ask questions:
decide on your own and go as far as you can.
Repo: ${repo}. Work in your own git worktree of that repo, never in its main
checkout: \`git -C ${repo} worktree add ${repo}/.ishikari/worktrees/${id} -B ishikari/${id}\`
(reuse the worktree if it exists, and start the branch from ${base} if it is new).
${prompt}
Commit your work on branch ishikari/${id}. Leave the worktree in place. Return status "stuck" if you cannot finish,
with what blocked you in notes.`,
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
    await post('bounty', [open[0], id, 'fixing', String(tries)])
    const fix = await detective(id, branch, open)
    if (!fix) continue
    const built = await worker(id, `Build this fix plan:\n${fix.plan}`, 'Fix')
    if (!built || built.status === 'stuck') continue
    const check = await inspect(id, branch)
    open = check ? check.bugs : open
    if (!open.length) {
      await post('bounty', [found[0], id, 'fixed', String(tries)])
      return { bugs: [], tries }
    }
  }
  await post('bounty', [found[0], id, 'escalated', String(MAX_TRIES)])
  return { bugs: open, tries: MAX_TRIES }
}

// A plan waits for the plans in its "after" list and builds on their branch.
const doneById = {}
async function runTask(p) {
  const id = p.id
  const deps = await Promise.all((p.after || []).map(d => doneById[d]))
  const blocked = deps.find(d => !d || d.status !== 'awaiting review')
  if (blocked) {
    await post('bulletin', [id, 'escalated', 'build script', '-'])
    return { id, branch: `ishikari/${id}`, status: 'escalated', bugs: [`blocked: ${blocked ? blocked.id : 'a plan it needs'} did not pass`], tries: 0 }
  }
  const base = deps.length ? deps[deps.length - 1].branch : 'main'
  const job = p.workflow
    ? `Run the saved workflow "${p.workflow}" as your job, with the plan in ${p.file}.`
    : `Build the plan in ${p.file}.`
  const built = await worker(id, job, 'Build', base)
  const branch = built ? built.branch : `ishikari/${id}`
  if (!built || built.status === 'stuck') {
    const why = built ? built.notes : 'worker ant died'
    await post('bounty', [`stuck: ${why}`, id, 'open', '0'])
    return finish(id, branch, await fixLoop(id, branch, [`stuck: ${why}`]))
  }
  await post('bulletin', [id, 'built', 'worker ant', '-'])
  await post('bulletin', [id, 'inspecting', 'inspector ant', '-'])
  const check = await inspect(id, branch)
  const found = check ? check.bugs : ['inspector ant died']
  if (!found.length) return finish(id, branch, { bugs: [], tries: 0 })
  await post('bulletin', [id, 'bugs', 'inspector ant', '-'])
  for (const b of found) await post('bounty', [b, id, 'open', '0'])
  return finish(id, branch, await fixLoop(id, branch, found))
}

async function finish(id, branch, result) {
  const status = result.bugs.length ? 'escalated' : 'awaiting review'
  await post('bulletin', [id, status, 'inspector ant', '-'])
  return { id, branch, status, bugs: result.bugs, tries: result.tries }
}

// Open bounties from a broken merge re-enter the fix loop directly.

plans.forEach(p => { doneById[p.id] = new Promise(r => { p.resolve = r }) })
const tasks = await parallel([
  ...plans.map(p => async () => { const r = await runTask(p); p.resolve(r); return r }),
  ...bugs.map(b => async () => finish(b.task, b.branch, await fixLoop(b.task, b.branch, [b.bug]))),
])

return { tasks: tasks.filter(Boolean) }
