export const meta = {
  name: 'ishikari-finish',
  description: 'Ishikari stage 3: merge the approved tasks in a straight line in a scratch copy, move main forward, run janitor and philosopher ants',
  whenToUse: 'After ishikari-build, with every passing task approved.',
  phases: [
    { title: 'Merge', detail: 'merger ant merges the approved tasks in a scratch copy and tests once' },
    { title: 'Upkeep', detail: 'janitor and philosopher ants, in parallel' },
    { title: 'Main', detail: 'main moves forward only if everything passed; worktrees cleaned up' },
  ],
}

// args: {
//   env: { repo, state, run, main, tool, testCommand?, checkCommand? },
//   approved: [{ id, branch, after? }],      passing tasks (from ishikari-build)
//   together?: { branch, sha, tasks },       ishikari-build's trial merge, reused when it matches
//   drop?: [{ id, branch }],                 tasks the user gave up on: removed
//   cleanup?: boolean,                       this run built a cleanup plan: no janitor, so
//                                            cleanups never chain
// }
// Returns { stage: 'finish', mainMoved, merged, notMoved, bugs, waiting, cleanup, critiques, check }
//      or { stage: 'error', reason }.
// bugs go into the next ishikari-build run; cleanup goes into the next
// ishikari-plan run as a suggested task.
//
// The repo's main checkout is touched once, at the end, by a fast-forward
// that git refuses if it would overwrite anything.

const EFFORT = { merger: 'medium', janitor: 'low', philosopher: 'low', finisher: 'low' }

const { env = {}, approved = [], together = null, drop = [], cleanup: isCleanup = false } = args
const bad = []
if (!/^\//.test(env.repo || '')) bad.push('env.repo must be an absolute path')
if (!/^\//.test(env.state || '')) bad.push('env.state must be an absolute path')
if (!/^\//.test(env.tool || '')) bad.push('env.tool must be an absolute path')
if (!/^[A-Za-z0-9._-]+$/.test(env.run || '')) bad.push('env.run must be a run id')
if (!/^[A-Za-z0-9._\/-]+$/.test(env.main || '')) bad.push('env.main must be a branch name')
if (bad.length) return { stage: 'error', reason: bad.join('; ') }

const treeOf = branch => `${env.state}/worktrees/${branch.replace(/\//g, '__')}`
const runOf = branch => String(branch).split('/')[1] || env.run
const where = `Repo: ${env.repo} (main branch: ${env.main}). Ishikari state folder: ${env.state}.
Use absolute paths only, and run git as \`git -C <path> ...\`. Never touch any other repo.`
const tests = env.testCommand ? `run the tests with \`${env.testCommand}\`` : 'run the repo\'s tests'
const scratch = `ishikari/${env.run}/_finish`
const scratchTree = treeOf(scratch)

async function twice(fn) {
  const first = await fn()
  return first != null ? first : fn()
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
        },
        required: ['id', 'outcome', 'detail'],
      },
    },
  },
  required: ['sha', 'results'],
}

// ---- merge order: every task after the tasks it is built on ----
const ids = new Set(approved.map(t => t.id))
const order = []
const placed = new Set()
const place = t => {
  if (placed.has(t.id)) return
  placed.add(t.id)
  ;(t.after || []).filter(d => ids.has(d)).forEach(d => place(approved.find(x => x.id === d)))
  order.push(t)
}
approved.forEach(place)

const results = {}
let sha = null
if (order.length) {
  phase('Merge')
  const sameSet = together && together.sha && Array.isArray(together.tasks) &&
    together.tasks.length === order.length && order.every(t => together.tasks.includes(t.id))
  const one = !sameSet && order.length === 1 && !(order[0].after || []).length ? order[0] : null
  const fast = one
    ? `Fast path: one task, already tested by its inspector. If
\`git -C ${env.repo} merge-base --is-ancestor ${env.main} ${one.branch}\` succeeds and
\`git -C ${env.repo} log --merges ${env.main}..${one.branch}\` prints nothing, create the worktree with
\`git -C ${env.repo} worktree add -b ${scratch} ${scratchTree} ${one.branch}\`, report the task
as "merged", return that commit as sha, and stop. Otherwise do the normal steps below.\n`
    : sameSet
    ? `Fast path: build's trial merge ${together.sha} already holds exactly these tasks
on top of ${env.main}, tested. If \`git -C ${env.repo} merge-base --is-ancestor ${env.main} ${together.sha}\`
succeeds, create the worktree with \`git -C ${env.repo} worktree add -b ${scratch} ${scratchTree} ${together.sha}\`,
report every task as "merged", return that commit as sha, and stop. Otherwise do the
normal steps below.\n`
    : ''
  const r = await twice(() => agent(
    `You are the merger ant of the Ishikari workflow.
${where}
Work only in a scratch worktree: ${scratchTree} on branch ${scratch}.
If that worktree or branch exists, remove them first
(\`git -C ${env.repo} worktree remove --force ${scratchTree}\`, \`git -C ${env.repo} branch -D ${scratch}\`).
${fast}Create it with \`git -C ${env.repo} worktree add -b ${scratch} ${scratchTree} ${env.main}\`.
Add each task's own commits on top, in a straight line with no merge commits,
one task at a time, in this order:
${order.map(t => `- ${t.id}: ${t.branch}${(t.after || []).length ? ` (built on ${t.after.join(', ')})` : ''}`).join('\n')}
A task built on other tasks needs them. If one of them was not merged here and is
not already in ${env.main} (\`git -C ${env.repo} merge-base --is-ancestor <its branch> ${env.main}\`;
its branch is named like the task's, with its own id), skip the task and report it
as "blocked".
For each, run \`git cherry-pick --empty=drop $(git -C ${env.repo} rev-list --reverse --no-merges --cherry-pick --right-only HEAD...<branch>)\`
inside the worktree. If it conflicts, run \`git cherry-pick --abort\`, reset the
scratch branch to where it was before this task, and report "conflict" with the files.
After all merges, ${tests} once inside ${scratchTree}. If they fail, find the first
task whose merge makes them fail (rebuild from ${env.main} and test after each
merge), report it as "tests failed", leave it and every task built on it out, and
go on until the tests pass.
Report every task. Never write or fix code yourself. Never touch ${env.main} or
the repo's main checkout. Return the final commit of ${scratch} as sha.`,
    { label: 'merger-ant', phase: 'Merge', effort: EFFORT.merger, schema: COMBINE },
  ))
  if (!r) return { stage: 'error', reason: `the merger ant died twice; main was not touched. Check ${scratchTree}.` }
  sha = r.sha
  for (const x of r.results || []) results[x.id] = x
}

// Check what the merger said against what was asked: nothing goes missing.
const merged = order.filter(t => results[t.id] && results[t.id].outcome === 'merged')
const failed = order.filter(t => results[t.id] && ['conflict', 'tests failed'].includes(results[t.id].outcome))
const waiting = order.filter(t => !merged.includes(t) && !failed.includes(t)).map(t => ({
  id: t.id, branch: t.branch, after: t.after || [],
  why: results[t.id] ? (results[t.id].detail || 'a task it is built on was not merged') : 'the merger did not report it',
}))
const bugs = failed.map(t => ({ task: t.id, branch: t.branch, after: t.after || [], kind: 'merge', bug: `merge failed (${results[t.id].outcome}): ${results[t.id].detail}` }))

// ---- upkeep on the merged result, before main moves ----
let cleanup = null
let critiques = []
if (merged.length) {
  phase('Upkeep')
  const names = merged.map(t => t.id).join(', ')
  const [jan, phil] = await parallel([
    () => isCleanup ? null : agent(
      `You are the janitor ant of the Ishikari workflow.
${where}
Read the merged code in ${scratchTree}. Find dead code, bloat and mess left by the
tasks just merged (${names}). Only worker ants write code, so if something needs
cleaning, write a complete cleanup plan a worker ant can build without questions
to ${env.state}/plans/${env.run}/cleanup.md. The plan starts from ${env.main} as it
is after this run: never name a worktree or a scratch branch as its base, they are
removed. Say it changes no behaviour. Change nothing else.`,
      { label: 'janitor-ant', phase: 'Upkeep', effort: EFFORT.janitor,
        schema: { type: 'object', properties: { needed: { type: 'boolean' }, title: { type: 'string' } }, required: ['needed', 'title'] } },
    ),
    () => agent(
      `You are the philosopher ant of the Ishikari workflow.
${where}
Read the merged code in ${scratchTree} and question the work just merged
(${names}) as a whole: design, scope, missing cases, how the tasks fit together.
Keep only your 5 most useful critiques, as short, concrete questions. Add them
with exactly this command, filling in the rows:
python3 ${env.tool} boards add ${env.state} critiques ${env.run} <<'ISHIKARI_ROWS_END'
[["<target file or task>", "<critique>"], ...]
ISHIKARI_ROWS_END
Return the same critiques in "critiques". Change nothing else, and never block the work.`,
      { label: 'philosopher-ant', phase: 'Upkeep', effort: EFFORT.philosopher,
        schema: { type: 'object', properties: { critiques: { type: 'array', items: { type: 'object', properties: { target: { type: 'string' }, critique: { type: 'string' } }, required: ['target', 'critique'] } } }, required: ['critiques'] } },
    ),
  ])
  if (phil && Array.isArray(phil.critiques)) critiques = phil.critiques
  if (jan && jan.needed) cleanup = { title: jan.title, file: `${env.state}/plans/${env.run}/cleanup.md` }
}

// ---- move main forward, clean up, write the bulletin ----
phase('Main')
const key = t => `${runOf(t.branch)}/${t.id}`
const rowsIf = moved => [
  ...merged.map(t => [key(t), moved ? 'done' : 'waiting', 'merger ant', '-']),
  ...failed.map(t => [key(t), 'merge failed', 'merger ant', '-']),
  ...waiting.map(t => [key(t), 'waiting', 'merger ant', '-']),
  ...drop.map(t => [key(t), 'dropped', 'user', '-']),
]
const write = rows => rows.length
  ? `python3 ${env.tool} boards write ${env.state} bulletin <<'ISHIKARI_ROWS_END'
${JSON.stringify(rows)}
ISHIKARI_ROWS_END`
  : '(nothing to write)'
const remove = [...merged.map(t => t.branch), ...drop.map(t => t.branch), `ishikari/${env.run}/_together`, scratch]
const FINISH = {
  type: 'object',
  properties: {
    moved: { type: 'boolean', description: `true if ${env.main} now points at the new commit` },
    reason: { type: 'string', description: 'if not moved, why' },
    check: {
      type: 'object',
      description: 'step 4 only',
      properties: { ran: { type: 'boolean' }, ok: { type: 'boolean' }, output: { type: 'string', description: 'last 20 lines' } },
      required: ['ran', 'ok', 'output'],
    },
  },
  required: ['moved', 'reason'],
}
const fin = await twice(() => agent(
  `You are Ishikari's finisher ant. Do these steps in order.
${where}
1. ${merged.length ? `Move ${env.main} forward to ${scratch}, only as a fast-forward:
   - Find where ${env.main} is checked out: \`git -C ${env.repo} worktree list --porcelain\`.
   - If it is checked out in some worktree, run \`git -C <that worktree> merge --ff-only ${scratch}\` there.
   - If it is checked out nowhere, run \`git -C ${env.repo} merge-base --is-ancestor ${env.main} ${scratch}\`,
     and only if that succeeds, \`git -C ${env.repo} branch -f ${env.main} ${scratch}\`.
   - If git refuses (main moved on, or local edits are in the way), stop moving: set
     moved to false and say why. Never reset, stash or discard anything.` : `Nothing was merged: leave ${env.main} alone (moved: false, reason: "nothing merged").`}
2. Only if step 1 moved ${env.main}, or nothing was merged: remove these worktrees and
   branches if they exist, with \`git -C ${env.repo} worktree remove --force <worktree>\`
   and \`git -C ${env.repo} branch -D <branch>\`. Each worktree is under
   ${env.state}/worktrees, named after its branch with "/" turned into "__".
${remove.map(b => `   - ${b}`).join('\n')}
3. If step 1 moved ${env.main}, or nothing was merged, run:
${write(rowsIf(true))}
   Otherwise run:
${write(rowsIf(false))}
4. ${env.checkCommand && merged.length ? `Only if step 1 moved ${env.main}: build and check the real app. Run
   \`${env.checkCommand}\` from the checkout of ${env.main} (the worktree found in step 1,
   else ${env.repo}), with a 600 s timeout. Report ran, ok (exit 0) and the last 20
   lines of output in check. Never fix anything.` : 'No app check: report check as {ran: false, ok: false, output: ""}.'}`,
  { label: 'finisher-ant', phase: 'Main', effort: EFFORT.finisher, schema: FINISH },
))

const mainMoved = Boolean(fin && fin.moved)
if (merged.length && !mainMoved) log(`main not moved: ${fin ? fin.reason : 'the finisher ant died twice'}`)
return {
  stage: 'finish',
  mainMoved,
  reason: fin ? fin.reason : 'the finisher ant died twice',
  sha,
  merged: mainMoved ? merged.map(t => t.id) : [],
  notMoved: mainMoved ? [] : merged.map(t => ({ id: t.id, branch: t.branch, after: t.after || [] })),
  bugs,
  waiting,
  cleanup,
  critiques,
  check: fin && fin.check ? fin.check : { ran: false, ok: false, output: '' },
}
