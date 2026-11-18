export const meta = {
  name: 'ishikari-finish',
  description: 'Ishikari stage 3: merge the approved tasks in a straight line in a scratch copy, build and check the janitor cleanup on top, let the judge score it against the plans, move main forward',
  whenToUse: 'After ishikari-build, with every passing task approved.',
  phases: [
    { title: 'Merge', detail: 'merger ant merges the approved tasks in a scratch copy and tests once' },
    { title: 'Upkeep', detail: 'janitor plans a cleanup, a worker builds it, an inspector checks it; then the judge scores the run, one fix round below 7' },
    { title: 'Main', detail: 'main moves forward only if everything passed; worktrees cleaned up' },
  ],
}

// args: {
//   env: { repo, state, run, main, tool, testCommand?, checkCommand? },
//   approved: [{ id, branch, after? }],      passing tasks (from ishikari-build)
//   together?: { branch, sha, tasks },       ishikari-build's trial merge, reused when it matches
//   drop?: [{ id, branch }],                 tasks dropped by the rules: marked dropped;
//                                            their branches are kept for a later look
//   cleanup?: boolean,                       this run built a dropped cleanup plan: no janitor,
//                                            so cleanups never chain
//   checkFixDone?: boolean,                  a check-fix round already ran (also true when a
//                                            task is named check-fix): a failed check is not
//                                            offered for a second round
// }
// Returns { stage: 'finish', mainMoved, merged, notMoved, bugs, waiting, cleanup, verdict, check,
//           checkFixDone, checkFix, checkFixRefused }
// checkFix: the bug for one check-fix build round ({task: 'check-fix', bug}) when the
// check failed and no round ran yet; null otherwise (checkFixRefused: true when the cap hit).
//      or { stage: 'error', reason }.
// bugs go into the next ishikari-build run. cleanup: {title, landed: true} when the
// janitor's cleanup was built, checked and landed with the tasks; {title, file,
// branch, landed: false, reason} when it was dropped, offered to the next
// ishikari-plan run as a suggested task. verdict: the judge ant's {score (0-10),
// gaps, fixed, flagged, first?, reason?}; flagged when the last score is below 7,
// and main moves anyway. null when nothing was merged.
//
// The repo's main checkout is touched once, at the end, by a fast-forward
// that git refuses if it would overwrite anything.

const EFFORT = { merger: 'medium', janitor: 'low', worker: 'medium', inspector: 'medium', detective: 'medium', judge: 'medium', finisher: 'low' }

const { env = {}, together = null, cleanup: isCleanup = false } = args
const items = v => Array.isArray(v) ? v.filter(t => t && typeof t === 'object').map(t => ({ ...t, id: String(t.id || ''), branch: String(t.branch || ''), after: Array.isArray(t.after) ? t.after.map(String) : [] })) : []
const approved = items(args.approved)
const drop = items(args.drop)
const checkFixDone = args.checkFixDone === true || [...approved, ...drop].some(t => t.id === 'check-fix')
const bad = []
if (args.checkFixDone != null && typeof args.checkFixDone !== 'boolean') bad.push('checkFixDone must be true or false')
for (const k of ['approved', 'drop']) if (args[k] != null && !Array.isArray(args[k])) bad.push(`${k} must be a list`)
// Branch names go into git commands: only Ishikari's own shape is allowed.
const BRANCH = /^ishikari\/[A-Za-z0-9._-]+\/[a-z0-9_][a-z0-9_-]{0,40}$/
const idsSeen = new Set()
for (const t of [...approved, ...drop]) {
  if (!BRANCH.test(t.branch)) bad.push(`task "${t.id}": bad branch "${t.branch}"`)
  if (idsSeen.has(t.id)) bad.push(`task "${t.id}" is listed twice`)
  idsSeen.add(t.id)
}
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
    fastPath: { type: 'boolean', description: 'true only if you took the fast path and stopped there' },
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
let trusted = false
if (order.length) {
  phase('Merge')
  const tog = together && typeof together.sha === 'string' && /^[0-9a-f]{7,64}$/.test(together.sha) &&
    Array.isArray(together.tasks) ? new Set(together.tasks.map(String)) : null
  const sameSet = Boolean(tog) && tog.size === order.length && order.every(t => tog.has(t.id))
  // Added tasks only: together must hold nothing outside this set (a task dropped
  // since build is inside it), and no task in it may be built on an added one
  // (it would have to come later in the line). Anything else: full merge.
  const added = tog && !sameSet && tog.size && [...tog].every(id => ids.has(id))
    ? order.filter(t => !tog.has(t.id)) : []
  const onTop = added.length && order.filter(t => tog.has(t.id)).every(t => !(t.after || []).some(d => added.some(a => a.id === d)))
    ? added : null
  const one = !sameSet && !onTop && order.length === 1 && !(order[0].after || []).length ? order[0] : null
  const fast = one
    ? `Fast path: one task, already tested by its inspector. If
\`git -C ${env.repo} merge-base --is-ancestor ${env.main} ${one.branch}\` succeeds and
\`git -C ${env.repo} log --merges ${env.main}..${one.branch}\` prints nothing, create the worktree with
\`git -C ${env.repo} worktree add -b ${scratch} ${scratchTree} ${one.branch}\`, report the task
as "merged", return that commit as sha, set fastPath to true, and stop. Otherwise do the normal steps below.\n`
    : sameSet
    ? `Fast path: build's trial merge ${together.sha} already holds exactly these tasks
on top of ${env.main}, tested. If \`git -C ${env.repo} merge-base --is-ancestor ${env.main} ${together.sha}\`
succeeds, and \`git -C ${env.repo} merge-base --is-ancestor <branch> ${together.sha}\` succeeds for
every branch below (no task moved on since), create the worktree with
\`git -C ${env.repo} worktree add -b ${scratch} ${scratchTree} ${together.sha}\`,
report every task as "merged", return that commit as sha, set fastPath to true, and stop.
If any check or the worktree add fails, do the normal steps below.\n`
    : onTop
    ? `Fast path: build's trial merge ${together.sha} already holds ${[...tog].join(', ')} on top
of ${env.main}, tested. If \`git -C ${env.repo} merge-base --is-ancestor ${env.main} ${together.sha}\`
succeeds, and \`git -C ${env.repo} merge-base --is-ancestor <branch> ${together.sha}\` succeeds for
each of ${order.filter(t => tog.has(t.id)).map(t => t.branch).join(', ')} (no task moved on since), create the worktree with \`git -C ${env.repo} worktree add -b ${scratch} ${scratchTree} ${together.sha}\`,
report those tasks as "merged", then add only these tasks on top, in this order, as
in the steps below: ${onTop.map(t => t.id).join(', ')}. ${tests[0].toUpperCase() + tests.slice(1)} once inside ${scratchTree}.
If they pass, return the final commit as sha and stop. If anything conflicts or the
tests fail, remove the worktree and branch and do the normal steps below from the start.
If any ancestor check or the worktree add fails, do the normal steps below.\n`
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
  // An exact fast path (the commit is the task's own tip, or the tested trial
  // merge after its ancestor checks) needs no second look.
  trusted = Boolean(r.fastPath === true && (one || sameSet))
  for (const x of r.results || []) if (x && typeof x === 'object') results[String(x.id)] = x
}

// Do not trust the report: git says which tasks' commits are in the scratch branch.
// \`git cherry\` matches by patch, so cherry-picked commits count. A dead or garbled
// answer falls back to the merger's report.
let landed = null
if (order.length && !trusted && typeof sha === 'string' && /^[0-9a-f]{7,64}$/.test(sha)) {
  const v = await agent(
    `Check which Ishikari task branches landed in a commit. Change nothing.
${where}
For each branch below, run \`git -C ${env.repo} cherry ${sha} <branch>\`. The task landed
if git succeeds and no output line starts with "+". Return the ids that landed in
"landed" and the rest in "missing".
${order.map(t => `- ${t.id}: ${t.branch}`).join('\n')}`,
    { label: 'verifier-ant', phase: 'Merge', effort: 'low',
      schema: { type: 'object', properties: { landed: { type: 'array', items: { type: 'string' } }, missing: { type: 'array', items: { type: 'string' } } }, required: ['landed', 'missing'] } },
  )
  if (v && Array.isArray(v.landed) && Array.isArray(v.missing)) {
    const l = new Set(v.landed.map(String)), m = new Set(v.missing.map(String))
    // Every task answered exactly once and nothing else, else the answer is not used.
    if (l.size + m.size === order.length && order.every(t => l.has(t.id) !== m.has(t.id))) landed = l
    else log('verifier answer does not match the tasks: using the merger report')
  } else log('verifier ant gave no answer: using the merger report')
}

// Check what the merger said against what was asked: nothing goes missing.
const said = t => results[t.id] && results[t.id].outcome
const merged = order.filter(t => landed ? landed.has(t.id) : said(t) === 'merged')
// Said merged but git disagrees (a conflict resolved by hand or a squash also
// looks like this): a merge bug, so build looks at it, not a silent wait.
const unproven = t => !merged.includes(t) && said(t) === 'merged'
const failed = order.filter(t => !merged.includes(t) && (unproven(t) || ['conflict', 'tests failed'].includes(said(t))))
const waiting = order.filter(t => !merged.includes(t) && !failed.includes(t)).map(t => ({
  task: t.id, id: t.id, branch: t.branch, after: t.after || [],
  bug: `not merged: ${results[t.id] ? (results[t.id].detail || 'a task it is built on was not merged') : 'the merger did not report it'}`,
}))
const bugs = failed.map(t => ({ task: t.id, branch: t.branch, after: t.after || [], kind: 'merge',
  bug: unproven(t) ? 'merge failed (conflict): the merger said merged, but git cherry finds its commits missing from the result; they may have been changed while merging'
    : `merge failed (${results[t.id].outcome}): ${results[t.id].detail}` }))

// ---- upkeep on the merged result, before main moves ----
// The janitor plans a cleanup of this run's mess; a worker ant builds it on top
// of the scratch branch, an inspector checks it, with one fix round (detective,
// worker, inspector). Passed: the scratch branch fast-forwards to it, so the
// cleanup lands as its own commits after the tasks. Failed: it is dropped, its
// branch kept, its plan offered next time. Then the judge ant scores the result.
let cleanup = null
let verdict = null
const PASS = 7
const planDir = `${env.state}/plans/${env.run}`
const fixBranch = `ishikari/${env.run}/_judgefix`
const fixTree = treeOf(fixBranch)
let fixKept = false
const cleanBranch = `ishikari/${env.run}/_cleanup`
const cleanTree = treeOf(cleanBranch)
const cleanPlan = `${env.state}/plans/${env.run}/cleanup.md`
let cleanKept = false
let readyFF = null
if (merged.length) {
  phase('Upkeep')
  const names = merged.map(t => t.id).join(', ')
  const janitorChain = async () => {
    const jan = isCleanup ? null : await agent(
      `You are the janitor ant of the Ishikari workflow.
${where}
Read the merged code in ${scratchTree}. Find dead code, bloat, duplication and mess
left by the tasks just merged (${names}), and only that: leave the rest of the repo
alone. Only worker ants write code, so if something needs cleaning, write a
complete cleanup plan a worker ant can build without questions to ${cleanPlan}.
A worker builds it now, on top of ${scratch}. Say it changes no behaviour, and
name the files it touches. Change nothing else.`,
      { label: 'janitor-ant', phase: 'Upkeep', effort: EFFORT.janitor,
        schema: { type: 'object', properties: { needed: { type: 'boolean' }, title: { type: 'string' } }, required: ['needed', 'title'] } },
    )
    if (jan && jan.needed) {
      const BUILT = { type: 'object', properties: { status: { type: 'string', enum: ['built', 'stuck'] }, notes: { type: 'string' } }, required: ['status', 'notes'] }
      const CHECKED = { type: 'object', properties: { bugs: { type: 'array', items: { type: 'string' } } }, required: ['bugs'] }
      const build = (extra) => agent(
        `You are a worker ant of the Ishikari workflow, building the janitor's cleanup.
${where}
Plan: ${cleanPlan}.${extra}
Work only in the worktree ${cleanTree} on branch ${cleanBranch}. If it does not exist,
create it with \`git -C ${env.repo} worktree add -b ${cleanBranch} ${cleanTree} ${scratch}\`.
Change no behaviour. Keep the tests passing (${tests} inside ${cleanTree}).
Commit your work on ${cleanBranch} in small commits, no merge commits. Never touch
${scratch}, ${env.main} or the repo's main checkout. Return "stuck" if you cannot.`,
        { label: extra ? 'worker-ant:cleanup:fix' : 'worker-ant:cleanup', phase: 'Upkeep', effort: EFFORT.worker, schema: BUILT },
      )
      const inspect = (round) => agent(
        `You are an inspector ant of the Ishikari workflow, checking the janitor's cleanup.
${where}
Plan: ${cleanPlan}. Code: ${cleanTree}, branch ${cleanBranch}, built on ${scratch}
(every task of this run, merged). Check that it follows the plan, changes no
behaviour and touches only this run's mess, then ${tests} inside ${cleanTree}:
these tests are the combined test. Return each problem in "bugs", or an empty
list. Never fix anything.`,
        { label: `inspector-ant:cleanup:${round}`, phase: 'Upkeep', effort: EFFORT.inspector, schema: CHECKED },
      )
      const drop = reason => ({ title: jan.title, file: cleanPlan, branch: cleanBranch, landed: false, reason })
      let b = await build('')
      let bugs = b && b.status === 'built' ? (await inspect(1) || { bugs: ['the inspector ant died'] }).bugs : [b ? 'worker stuck: ' + b.notes : 'the worker ant died']
      if (bugs.length) {
        const det = await agent(
          `You are the detective ant of the Ishikari workflow. The janitor's cleanup failed its check.
${where}
Plan: ${cleanPlan}. Code: ${cleanTree}, branch ${cleanBranch}. Bugs:
${bugs.map(x => `- ${x}`).join('\n')}
Find why, and write the fix plan in "plan" for a worker ant. Never write code.`,
          { label: 'detective-ant:cleanup', phase: 'Upkeep', effort: EFFORT.detective,
            schema: { type: 'object', properties: { cause: { type: 'string' }, plan: { type: 'string' } }, required: ['cause', 'plan'] } },
        )
        b = det ? await build(`\nIt failed its check. Fix plan from the detective ant:\n${det.plan}`) : null
        bugs = b && b.status === 'built' ? (await inspect(2) || { bugs: ['the inspector ant died'] }).bugs : ['fix not built']
      }
      if (bugs.length) {
        cleanup = drop(bugs.join('; '))
        cleanKept = true
      } else readyFF = jan
    }
  }
  const fastForwardTo = async (branch, label) => {
    const ff = await agent(
      `Fast-forward the Ishikari scratch branch to the checked branch ${branch}.
${where}
Run \`git -C ${scratchTree} merge --ff-only ${branch}\`. If git refuses, change
nothing and set ok to false. Return the new commit of ${scratch} as sha.`,
      { label, phase: 'Upkeep', effort: 'low',
        schema: { type: 'object', properties: { ok: { type: 'boolean' }, sha: { type: 'string' } }, required: ['ok', 'sha'] } },
    )
    if (ff && ff.ok) { sha = ff.sha || sha; return true }
    return false
  }
  const fastForward = async () => {
    if (await fastForwardTo(cleanBranch, 'merger-ant:cleanup')) cleanup = { title: readyFF.title, landed: true }
    else { cleanup = { title: readyFF.title, file: cleanPlan, branch: cleanBranch, landed: false, reason: 'could not fast-forward the scratch branch' }; cleanKept = true }
  }
  // The judge ant scores the whole run, cleanup included, against the plans.
  // Below PASS: one fix round (worker, inspector), then a second score. Still
  // below PASS: main moves anyway and the report flags it.
  const judgeOnce = async (round) => {
    const j = await agent(
      `You are the judge ant of the Ishikari workflow.
${where}
Read the plans for this run in ${planDir}: investigation_report.md (the user's task
and goal), architecture.md and every worker plan. Then read the merged code in
${scratchTree}, the code that will land on ${env.main}: the tasks (${names}) with the
janitor's cleanup on top if it landed.
Judge one thing: does the implementation match the plans? Score the whole run from
0 to 10, where 10 means every planned behaviour is built as planned and nothing
unplanned was added. List each gap in "gaps" as a short, concrete fix a worker ant
can build without questions: what is missing or wrong, and in which file.
Never change anything.`,
      { label: `judge-ant:${round}`, phase: 'Upkeep', effort: EFFORT.judge,
        schema: { type: 'object', properties: { score: { type: 'integer', minimum: 0, maximum: 10 }, gaps: { type: 'array', items: { type: 'string' } } }, required: ['score', 'gaps'] } },
    )
    return j && Number.isInteger(j.score) ? { score: Math.max(0, Math.min(10, j.score)), gaps: Array.isArray(j.gaps) ? j.gaps.map(String) : [] } : null
  }
  const judgeRun = async () => {
    const first = await judgeOnce(1)
    if (!first) { verdict = { score: null, gaps: [], fixed: false, flagged: true, reason: 'the judge ant died' }; return }
    verdict = { score: first.score, gaps: first.gaps, fixed: false, flagged: first.score < PASS }
    if (first.score >= PASS || !first.gaps.length) return
    const BUILT = { type: 'object', properties: { status: { type: 'string', enum: ['built', 'stuck'] }, notes: { type: 'string' } }, required: ['status', 'notes'] }
    const b = await agent(
      `You are a worker ant of the Ishikari workflow, closing the judge ant's gaps.
${where}
The judge scored the run ${first.score}/10 against the plans in ${planDir}. Gaps:
${first.gaps.map(g => `- ${g}`).join('\n')}
Work only in the worktree ${fixTree} on branch ${fixBranch}. If it does not exist,
create it with \`git -C ${env.repo} worktree add -b ${fixBranch} ${fixTree} ${scratch}\`.
Close the gaps so the code matches the plans. Keep the tests passing (${tests} inside
${fixTree}). Commit on ${fixBranch} in small commits, no merge commits. Never touch
${scratch}, ${env.main} or the repo's main checkout. Return "stuck" if you cannot.`,
      { label: 'worker-ant:judge-fix', phase: 'Upkeep', effort: EFFORT.worker, schema: BUILT },
    )
    let bugs = ['the worker ant died']
    if (b && b.status === 'built') {
      const c = await agent(
        `You are an inspector ant of the Ishikari workflow, checking the fix for the judge ant's gaps.
${where}
Gaps:
${first.gaps.map(g => `- ${g}`).join('\n')}
Code: ${fixTree}, branch ${fixBranch}, built on ${scratch}. Check that it closes the gaps
and breaks nothing, then ${tests} inside ${fixTree}. Return each problem in "bugs", or
an empty list. Never fix anything.`,
        { label: 'inspector-ant:judge-fix', phase: 'Upkeep', effort: EFFORT.inspector,
          schema: { type: 'object', properties: { bugs: { type: 'array', items: { type: 'string' } } }, required: ['bugs'] } },
      )
      bugs = c ? c.bugs : ['the inspector ant died']
    } else if (b) bugs = ['worker stuck: ' + b.notes]
    if (bugs.length || !(await fastForwardTo(fixBranch, 'merger-ant:judge-fix'))) { fixKept = true; verdict.reason = bugs.join('; ') || 'could not fast-forward the scratch branch'; return }
    const second = await judgeOnce(2)
    verdict = second
      ? { score: second.score, gaps: second.gaps, fixed: true, flagged: second.score < PASS, first: first.score }
      : { ...verdict, fixed: true, reason: 'the judge ant died on its second look' }
  }
  await janitorChain()
  if (readyFF) await fastForward()
  await judgeRun()
}

// ---- move main forward, clean up, write the bulletin ----
phase('Main')
const key = t => `${runOf(t.branch)}/${t.id}`
const rowsIf = moved => [
  ...merged.map(t => [key(t), moved ? 'done' : 'waiting', 'merger ant', '-']),
  ...failed.map(t => [key(t), 'merge failed', 'merger ant', '-']),
  ...waiting.map(t => [key(t), 'waiting', 'merger ant', '-']),
  ...drop.map(t => [key(t), 'dropped', 'main session', '-']),
]
const write = rows => rows.length
  ? `python3 ${env.tool} boards write ${env.state} bulletin <<'ISHIKARI_ROWS_END'
${JSON.stringify(rows)}
ISHIKARI_ROWS_END`
  : '(nothing to write)'
const remove = [...merged.map(t => t.branch), `ishikari/${env.run}/_together`, scratch, ...(cleanKept ? [] : [cleanBranch]), ...(fixKept ? [] : [fixBranch])]
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

const check = fin && fin.check ? fin.check : { ran: false, ok: false, output: '' }
const mainMoved = Boolean(merged.length && fin && fin.moved === true)
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
  verdict,
  check,
  checkFixDone,
  checkFix: check.ran && !check.ok && !checkFixDone ? { task: 'check-fix', bug: check.output || 'the app check failed' } : null,
  checkFixRefused: Boolean(check.ran && !check.ok && checkFixDone),
}
