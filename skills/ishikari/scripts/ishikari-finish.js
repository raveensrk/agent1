export const meta = {
  name: 'ishikari-finish',
  description: 'Ishikari stage 3: merge the approved tasks in a straight line in a scratch copy, the janitor cleans up on top, the judge scores it against the product spec, the docs ant updates the docs, move main forward',
  whenToUse: 'After ishikari-build, with every passing task approved.',
  phases: [
    { title: 'Merge', detail: 'merger ant merges the approved tasks in a scratch copy and tests once' },
    { title: 'Upkeep', detail: 'janitor cleans up, tests and commits itself; the judge scores the run, one fix round below 7 or for its bugs; then the docs ant updates the docs with /docs' },
    { title: 'Main', detail: 'main moves forward only if everything passed; worktrees cleaned up' },
  ],
}

// args: {
//   env: { repo, state, run, main, tool, testCommand?, checkCommand? },
//   approved: [{ id, branch, after? }],      passing tasks (from ishikari-build)
//   together?: { branch, sha, tasks },       ishikari-build's trial merge, reused when it matches
//   drop?: [{ id, branch }],                 tasks dropped by the rules: marked dropped;
//                                            their branches are kept for a later look
//   round?: number,                          this run's nth finish (default 1): later
//                                            rounds use their own upkeep branches, so kept
//                                            branches of an earlier round are never removed
//   landed?: string[],                       task ids an earlier finish of this run put on main
//   parallel?: number,                       juror ants at once, 1 to 5 (default 1)
//   cleanup?: boolean,                       this run built a dropped cleanup plan: no janitor,
//                                            so cleanups never chain
//   checkFixDone?: boolean,                  a check-fix round already ran (also true when a
//                                            task is named check-fix): a failed check is not
//                                            offered for a second round
// }
// Returns { stage: 'finish', mainMoved, merged, notMoved, bugs, waiting, docs, cleanup, verdict, upkeepStopped, check,
//           checkFixDone, checkFix, checkFixRefused, log }
// log holds the stage's logbook entries; `ishikari.py save` appends them.
// checkFix: the bug for one check-fix build round ({task: 'check-fix', bug}) when the
// check failed and no round ran yet; null otherwise (checkFixRefused: true when the cap hit).
//      or { stage: 'error', reason }.
// bugs go into the next ishikari-build run. docs: null when there was nothing to
// update; {title, landed: true}, or {title, branch, landed: false, reason} with the
// branch kept. cleanup: {title, landed: true} when the
// janitor's cleanup was built, checked and landed with the tasks; {title, file,
// branch, landed: false, reason} when it was dropped, offered to the next
// ishikari-plan run as a suggested task. verdict: the judge ant's {score (0-10),
// gaps, fixed, flagged, first?, reason?}; flagged when the last score is below 7,
// and main moves anyway. null when nothing was merged.
//
// The repo's main checkout is touched once, at the end, by a fast-forward
// that git refuses if it would overwrite anything.

// For now every ant runs on the latest Opus at low effort. To tune one ant,
// change its entry here.
const MODEL = 'opus'
const EFFORT = { merger: 'low', docs: 'low', janitor: 'low', worker: 'low', detective: 'low', judge: 'low', juror: 'low', finisher: 'low' }

const { env = {}, together = null, cleanup: isCleanup = false } = args
const items = v => Array.isArray(v) ? v.filter(t => t && typeof t === 'object').map(t => ({ ...t, id: String(t.id || ''), branch: String(t.branch || ''), after: Array.isArray(t.after) ? t.after.map(String) : [] })) : []
const approved = items(args.approved)
const drop = items(args.drop)
const round = Number.isInteger(args.round) && args.round > 1 ? args.round : 1  // this run's nth finish
const sfx = round > 1 ? `-${round}` : ''
// Tasks an earlier finish of this run already put on main: their branches are gone.
const earlier = Array.isArray(args.landed) ? args.landed.map(String).filter(x => /^[a-z0-9][a-z0-9_-]{0,40}$/.test(x)) : []
const isSha = x => typeof x === 'string' && /^[0-9a-f]{7,64}$/.test(x)
const checkFixDone = args.checkFixDone === true || [...approved, ...drop].some(t => t.id === 'check-fix')
const bad = []
if (args.checkFixDone != null && typeof args.checkFixDone !== 'boolean') bad.push('checkFixDone must be true or false')
if (args.round != null && !(Number.isInteger(args.round) && args.round >= 1)) bad.push('round must be a whole number from 1')
if (args.landed != null && !Array.isArray(args.landed)) bad.push('landed must be a list of task ids')
if (args.parallel != null && !(Number.isInteger(args.parallel) && args.parallel >= 1 && args.parallel <= 5)) bad.push('parallel must be a whole number from 1 to 5')
for (const k of ['approved', 'drop']) if (args[k] != null && !Array.isArray(args[k])) bad.push(`${k} must be a list`)
// Branch names go into git commands: only Ishikari's own shape is allowed, and
// never a scratch branch (their names start with "_").
const BRANCH = /^ishikari\/[A-Za-z0-9._-]+\/[a-z0-9][a-z0-9_-]{0,40}$/
const idsSeen = new Set()
for (const t of [...approved, ...drop]) {
  if (!BRANCH.test(t.branch)) bad.push(`task "${t.id}": bad branch "${t.branch}"`)
  if (idsSeen.has(t.id)) bad.push(`task "${t.id}" is listed twice`)
  idsSeen.add(t.id)
}
// Paths, the branch and the commands go into shell commands inside the ants'
// prompts: only safe characters are let through (ishikari.py setup checks too).
for (const k of ['repo', 'state', 'tool']) if (!/^\/[A-Za-z0-9._\/+-]+$/.test(env[k] || '')) bad.push(`env.${k} must be an absolute path of letters, digits and . _ / + -`)
if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(env.run || '')) bad.push('env.run must be a run id')
if (!/^[A-Za-z0-9._][A-Za-z0-9._\/-]*$/.test(env.main || '')) bad.push('env.main must be a branch name')
for (const k of ['testCommand', 'checkCommand']) if (env[k] != null && (typeof env[k] !== 'string' || /[\n\r`]/.test(env[k]))) bad.push(`env.${k} must be one line with no backtick`)
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

// ---- logbook entries: kept here, returned as the result's log ----
// A workflow cannot touch files, so no ant writes the logbook: the main
// session's `ishikari.py save` of this result appends the log, with no ant.
// One rule for "this upkeep work landed", used by the code and the logbook:
// the ant says landed, its checks passed and it names the new commit. The docs
// ant must also show it touched docs only.
const DOC_FILE = f => typeof f === 'string' && !f.includes('..') && (/^docs?\//.test(f) || /\.(md|org)$/.test(f))
const accepted = (kind, r) => Boolean(r && r.changed === true && r.landed === true && r.testsPassed === true && isSha(r.sha) &&
  (kind !== 'docs-ant' || (Array.isArray(r.files) && r.files.length > 0 && r.files.every(DOC_FILE))))
const summarize = (kind, r) => {
  if (r == null) return 'died'
  if (Array.isArray(r.bugs)) return r.bugs.length ? `${r.bugs.length} bug${r.bugs.length > 1 ? 's' : ''} found` : r.landed === false ? 'passed, not landed' : 'passed'
  if (typeof r.status === 'string') return r.status
  if (Number.isInteger(r.score)) return `score ${r.score}`
  if (Array.isArray(r.results)) return `merged ${r.results.filter(x => x && x.outcome === 'merged').length} of ${r.results.length}`
  if (typeof r.changed === 'boolean') return !r.changed ? 'nothing changed' : accepted(kind, r) ? 'landed' : 'dropped'
  if (typeof r.moved === 'boolean') return r.moved ? 'main moved' : 'main not moved'
  return 'finished'
}
const entries = []
const logNow = rows => entries.push(...rows)
async function ant(prompt, opts) {
  // A call that throws is a dead ant: it never takes the whole stage down.
  const r = await agent(prompt, { ...opts, model: MODEL }).catch(() => null)
  const [kind, a, b] = String(opts.label).split(':')
  if (kind === 'finisher-ant') return r  // the stage's summary rows stand for it
  const task = kind === 'juror-ant' ? b : ['worker-ant', 'detective-ant'].includes(kind) && a ? a : undefined
  logNow([{ run: env.run, ...(task ? { task } : {}), who: kind.replace('-ant', ' ant'), event: summarize(kind, r),
    ...(r != null ? { detail: JSON.stringify(r).slice(0, 400) } : {}) }])
  return r
}

const COMBINE = {
  type: 'object',
  properties: {
    sha: { type: 'string', description: 'final commit of the scratch branch' },
    fastPath: { type: 'boolean', description: 'true only if you took the fast path and stopped there' },
    landed: { type: 'array', items: { type: 'string' }, description: 'task ids git cherry finds in sha' },
    missing: { type: 'array', items: { type: 'string' }, description: 'task ids git cherry does not find in sha' },
    lines: { type: 'integer', description: `lines added plus lines deleted between ${'main'} and sha` },
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

const results = Object.create(null)  // keyed by task id: no prototype, so "constructor" is a plain key
let sha = null
let trusted = false
let merge = null
let linesChanged = null  // from the merger's git diff --shortstat; null if it gave none
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
    ? `Fast path: one task, already tested by its detective. If
\`git -C ${env.repo} merge-base --is-ancestor ${env.main} ${one.branch}\` succeeds and
\`git -C ${env.repo} log --merges ${env.main}..${one.branch}\` prints nothing, create the worktree with
\`git -C ${env.repo} worktree add -b ${scratch} ${scratchTree} ${one.branch}\`, report the task
as "merged", return that commit as sha, set fastPath to true, and stop. Otherwise do the normal steps below.\n`
    : sameSet
    ? `Fast path: build's trial merge ${together.sha} already holds exactly these tasks
on top of ${env.main}, tested. If \`git -C ${env.repo} merge-base --is-ancestor ${env.main} ${together.sha}\`
succeeds, and \`git -C ${env.repo} cherry ${together.sha} <branch>\` succeeds and prints no line
starting with "+" for every branch below (no task moved on since), create the worktree with
\`git -C ${env.repo} worktree add -b ${scratch} ${scratchTree} ${together.sha}\`,
report every task as "merged", return that commit as sha, set fastPath to true, and stop.
If any check or the worktree add fails, do the normal steps below.\n`
    : onTop
    ? `Fast path: build's trial merge ${together.sha} already holds ${[...tog].join(', ')} on top
of ${env.main}, tested. If \`git -C ${env.repo} merge-base --is-ancestor ${env.main} ${together.sha}\`
succeeds, and \`git -C ${env.repo} cherry ${together.sha} <branch>\` succeeds and prints no line
starting with "+" for each of ${order.filter(t => tog.has(t.id)).map(t => t.branch).join(', ')} (no task moved on since), create the worktree with \`git -C ${env.repo} worktree add -b ${scratch} ${scratchTree} ${together.sha}\`,
report those tasks as "merged", then add only these tasks on top, in this order, as
in the steps below: ${onTop.map(t => t.id).join(', ')}. ${tests[0].toUpperCase() + tests.slice(1)} once inside ${scratchTree}.
If they pass, return the final commit as sha and stop. If anything conflicts or the
tests fail, remove the worktree and branch and do the normal steps below from the start.
If any check or the worktree add fails, do the normal steps below.\n`
    : ''
  const r = await twice(() => ant(
    `You are the merger ant of the Ishikari workflow.
${where}
Work only in a scratch worktree: ${scratchTree} on branch ${scratch}.
If that worktree or branch exists, remove them first
(\`git -C ${env.repo} worktree remove --force ${scratchTree}\`, \`git -C ${env.repo} branch -D ${scratch}\`).
${fast}Create it with \`git -C ${env.repo} worktree add -b ${scratch} ${scratchTree} ${env.main}\`.
Add each task's own commits on top, in a straight line with no merge commits,
one task at a time, in this order:
${order.map(t => `- ${t.id}: ${t.branch}${(t.after || []).length ? ` (built on ${t.after.join(', ')})` : ''}`).join('\n')}
A task built on other tasks needs them. A needed task counts as already in
${env.main} when ${earlier.length ? `its id is one of ${earlier.join(', ')} (an earlier finish of this run landed it), or when ` : ''}its branch exists (named like the task's, with its own id) and
\`git -C ${env.repo} cherry ${env.main} <its branch>\` succeeds and prints no line starting with "+".
If a needed task was not merged here and is not already in ${env.main}, skip the
task and report it as "blocked".
For each, run \`commits=$(git -C ${env.repo} rev-list --reverse --no-merges --cherry-pick --right-only HEAD...<branch>); if [ -n "$commits" ]; then git cherry-pick --empty=drop $commits; fi\`
inside the worktree. If it conflicts, run \`git cherry-pick --abort\`, reset the
scratch branch to where it was before this task, and report "conflict" with the files.
After all merges, ${tests} once inside ${scratchTree}. If they fail, find the first
task whose merge makes them fail (rebuild from ${env.main} and test after each
merge), report it as "tests failed", leave it and every task built on it out, and
go on until the tests pass.
Report every task. Never write or fix code yourself. Never touch ${env.main} or
the repo's main checkout. Return the final commit of ${scratch} as sha.
Last, even after a fast path, check your own work with git, never from memory:
- For each task branch, run \`git -C ${env.repo} cherry <sha> <branch>\`. The task landed if
  git succeeds and no output line starts with "+". Put landed ids in "landed" and
  every other task id in "missing".
- Run \`git -C ${env.repo} diff --shortstat ${env.main} <sha>\` and return insertions plus
  deletions as "lines" (0 if it prints nothing).`,
    { label: 'merger-ant', phase: 'Merge', effort: EFFORT.merger, schema: COMBINE },
  ))
  if (!r) { return { log: entries, stage: 'error', reason: `the merger ant died twice; main was not touched. Check ${scratchTree}.` } }
  sha = isSha(r.sha) ? r.sha : null
  // An exact fast path (the commit is the task's own tip, or the tested trial
  // merge after its ancestor checks) needs no second look.
  trusted = Boolean(r.fastPath === true && (one || sameSet))
  for (const x of r.results || []) if (x && typeof x === 'object') results[String(x.id)] = x
  if (Number.isInteger(r.lines) && r.lines >= 0) linesChanged = r.lines
  merge = r
}

// The merger's own git cherry check says which tasks' commits are in the scratch
// branch. \`git cherry\` matches by patch, so cherry-picked commits count. A
// missing or garbled check falls back to the merger's outcome report.
let landed = null
if (order.length && !trusted && merge && Array.isArray(merge.landed) && Array.isArray(merge.missing)) {
  const l = new Set(merge.landed.map(String)), m = new Set(merge.missing.map(String))
  // Every task answered exactly once and nothing else, else the check is not used.
  if (l.size + m.size === order.length && order.every(t => l.has(t.id) !== m.has(t.id))) landed = l
  else log('merger git cherry check does not match the tasks: using its outcome report')
} else if (order.length && !trusted) log('merger gave no git cherry check: using its outcome report')

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

// Tasks count as merged only with a commit to move main to.
if (merged.length && !sha) { return { log: entries, stage: 'error', reason: `the merger ant reported merged tasks but gave no commit for ${scratch}; main was not touched. Check ${scratchTree}.` } }

// ---- upkeep on the merged result, before main moves ----
// The janitor cleans up this run's mess itself, in its own worktree on top of
// the scratch branch: it edits, runs the tests, commits, and fast-forwards the
// scratch branch to its cleanup only if they pass. No other ant takes part.
// Failed: the cleanup is dropped, its branch kept, its note offered next time.
// Then the judge ant scores the result.
let cleanup = null
let docs = null
let verdict = null
const PASS = 7
const MAX_JURORS = Number.isInteger(args.parallel) ? args.parallel : 1  // juror ants at once: one unless parallel is set
const MIN_JURY = 3    // fewer merged tasks: the judge works alone
const JANITOR_MIN_LINES = 100  // fewer lines added or changed: no janitor
const planDir = `${env.state}/plans/${env.run}`
const fixBranch = `ishikari/${env.run}/_judgefix${sfx}`
const fixTree = treeOf(fixBranch)
let fixKept = false
const cleanBranch = `ishikari/${env.run}/_cleanup${sfx}`
const cleanTree = treeOf(cleanBranch)
const cleanPlan = `${env.state}/plans/${env.run}/cleanup${sfx}.md`
let cleanKept = false
const docsBranch = `ishikari/${env.run}/_docs${sfx}`
let docsKept = false
let upkeepStopped = ''  // set when the scratch copy could not be put back: no more upkeep
const docsTree = treeOf(docsBranch)
if (merged.length) {
  phase('Upkeep')
  const names = merged.map(t => t.id).join(', ')
  // Upkeep work that is not accepted must not stay on the scratch copy: the
  // ant may have fast-forwarded it before failing or dying. Put it back to the
  // last checked commit. If that fails, upkeep stops; main still moves only to
  // the checked commit, never to the scratch branch by name.
  const rewind = async (what) => {
    const good = sha
    const r = await ant(
      `Put the Ishikari scratch branch back: ${what} was not accepted.
${where}
Run \`git -C ${scratchTree} reset --hard ${good}\`, then \`git -C ${scratchTree} rev-parse HEAD\`
and return its output as sha. Touch nothing else.`,
      { label: 'merger-ant:rewind', phase: 'Upkeep', effort: 'low',
        schema: { type: 'object', properties: { sha: { type: 'string' } }, required: ['sha'] } },
    )
    const ok = Boolean(r && isSha(r.sha) && (r.sha.startsWith(good) || good.startsWith(r.sha)))
    if (!ok) { upkeepStopped = `the scratch copy could not be put back to ${good} after ${what}`; log(`upkeep stopped: ${upkeepStopped}`) }
    return ok
  }
  // The docs ant runs last, on the final code, in its own worktree and branch:
  // the /docs skill in update mode, or in create mode when the repo has no docs
  // folder. It never asks: the investigator's docs brief, written while
  // planning, holds the user's answers. It lands only if the docs check and the
  // tests pass and it touched docs only. Dropped: branch kept, main moves without it.
  const docsChain = async () => {
    if (upkeepStopped) return
    const d = await ant(
      `You are the docs ant of the Ishikari workflow. You write or update the repo's
docs for the tasks just merged (${names}) and commit them yourself.
${where}
The docs brief ${planDir}/docs_brief.md holds what the user answered about the
docs while the run was planned. Read it first, with the product spec
${planDir}/product_spec.md and the tech spec ${planDir}/tech_spec.md. If the brief
does not exist, work from the two specs and the code.
1. If the worktree ${docsTree} or the branch ${docsBranch} exists, remove them first. Then
   \`git -C ${env.repo} worktree add -b ${docsBranch} ${docsTree} ${sha}\`.
2. In ${docsTree}: with a docs/ or doc/ folder, use the /docs skill in update mode,
   scoped to the commits from ${env.main} to ${sha}. With neither folder, use the
   /docs skill in create mode and write docs/ from scratch: the brief stands in
   for the skill's interview and for its OK on the outline, so decide the
   outline yourself and go on. Work on ${docsBranch}, never on a docs-book branch.
   Never ask the user: put open questions in the docs'
   Open questions chapter, or leave them out if it has none. Skip the docs-only
   rebuild test. Never install a tool: use what is installed and name each
   skipped step in reason. Move or delete a root note only where the brief says so. Change only files under docs/ or doc/, and Markdown or Org files
   elsewhere; never code, tests or data. If something else needs a change, say so
   in reason and leave it.
3. If docs/build.sh or doc/build.sh exists, run its \`diagrams\` and \`check\` commands;
   then ${tests} inside ${docsTree}.
4. Commit on ${docsBranch} in small commits, no merge commits. Return every changed
   path in files: the output of \`git -C ${docsTree} diff --name-only ${sha} ${docsBranch}\`.
5. Only if every check passes: \`git -C ${scratchTree} merge --ff-only ${docsBranch}\`, and
   return the new commit of ${scratch} as sha. Otherwise leave ${scratch} alone and
   say why in reason.
Never touch ${env.main} or the repo's main checkout.`,
      { label: 'docs-ant', phase: 'Upkeep', effort: EFFORT.docs,
        schema: { type: 'object', properties: {
          changed: { type: 'boolean' }, title: { type: 'string' }, testsPassed: { type: 'boolean' },
          landed: { type: 'boolean', description: `true only if ${scratch} was fast-forwarded to the docs update` },
          files: { type: 'array', items: { type: 'string' }, description: 'every path the update changed' },
          sha: { type: 'string' }, reason: { type: 'string' },
        }, required: ['changed', 'title', 'testsPassed', 'landed', 'files'] } },
    )
    if (d && d.changed === false) return
    if (accepted('docs-ant', d)) { docs = { title: String(d.title || ''), landed: true }; sha = d.sha; return }
    docsKept = true
    const outside = d && Array.isArray(d.files) ? d.files.filter(f => !DOC_FILE(f)) : []
    docs = { title: d ? String(d.title || '') : '', branch: docsBranch, landed: false,
      reason: !d ? 'the docs ant died'
        : outside.length ? `it changed files that are not docs: ${outside.slice(0, 5).join(', ')}`
        : d.reason || (d.testsPassed ? 'the scratch branch was not fast-forwarded, or no commit or file list was given' : 'a check failed') }
    await rewind('the docs update')
  }
  const janitorChain = async () => {
    const small = linesChanged != null && linesChanged < JANITOR_MIN_LINES
    if (small) log(`janitor skipped: ${linesChanged} lines changed, under ${JANITOR_MIN_LINES}`)
    if (isCleanup || small || upkeepStopped) return
    const jan = await ant(
      `You are the janitor ant of the Ishikari workflow. You clean up and commit
the cleanup yourself; no other ant checks it, so be careful and small.
${where}
Load the /janitor-ant skill and follow its Ishikari mode (if it is unavailable, read
${String(env.tool || '').replace(/\/ishikari\/scripts\/[^/]+$/, '')}/janitor-ant/SKILL.md). Its scope: the changes from ${env.main} to ${sha},
left by the tasks just merged (${names}). Read the merged code in ${scratchTree}.
If nothing needs cleaning, change nothing and set changed to false.
Otherwise:
1. If the worktree ${cleanTree} or the branch ${cleanBranch} exists, remove them first. Then
   \`git -C ${env.repo} worktree add -b ${cleanBranch} ${cleanTree} ${sha}\`.
2. Make the cleanup there, then ${tests} inside ${cleanTree}.
3. Commit on ${cleanBranch} in small commits, no merge commits. Write what you
   changed and why, in a few lines, to ${cleanPlan}.
4. Only if the tests pass: \`git -C ${scratchTree} merge --ff-only ${cleanBranch}\`, and
   return the new commit of ${scratch} as sha. If the tests fail or git refuses,
   leave ${scratch} alone and say why in reason.
Never touch ${env.main} or the repo's main checkout.`,
      { label: 'janitor-ant', phase: 'Upkeep', effort: EFFORT.janitor,
        schema: { type: 'object', properties: {
          changed: { type: 'boolean' }, title: { type: 'string' }, testsPassed: { type: 'boolean' },
          landed: { type: 'boolean', description: `true only if ${scratch} was fast-forwarded to the cleanup` },
          sha: { type: 'string' }, reason: { type: 'string' },
        }, required: ['changed', 'title', 'testsPassed', 'landed'] } },
    )
    if (jan && jan.changed === false) return
    if (accepted('janitor-ant', jan)) { cleanup = { title: String(jan.title || ''), landed: true }; sha = jan.sha; return }
    cleanKept = true
    // A dead janitor left no note to offer: only its branch is kept.
    if (jan) cleanup = { title: String(jan.title || ''), file: cleanPlan, branch: cleanBranch, landed: false,
      reason: jan.reason || (jan.testsPassed ? 'the scratch branch was not fast-forwarded, or no commit was given' : 'the tests failed') }
    await rewind('the cleanup')
  }
  // The judge ant scores the whole run, cleanup included, against the product spec.
  // Below PASS: one fix round (worker, detective) for every gap, then a second
  // score. At PASS or above: the same round, only for the gaps the judge calls
  // bugs (wrong behaviour); a missing or weak test alone starts no round. The
  // detective lands the fix itself, by fast-forward, only if it found no bug and
  // the tests pass: no other ant takes part. Still below PASS: main moves anyway
  // and the report flags it.
  // MIN_JURY or more tasks: the judge delegates, one juror ant per task (at most
  // MAX_JURORS at once), and decides the run's score from their reports.
  const SCORED = { type: 'object', properties: { score: { type: 'integer', minimum: 0, maximum: 10 }, gaps: { type: 'array', items: { type: 'string' } },
    bugs: { type: 'array', items: { type: 'string' }, description: 'the gaps, word for word, where the shipped code behaves wrongly; a missing or weak test is a gap, never a bug' } }, required: ['score', 'gaps'] }
  const juror = (t, round) => ant(
    `You are a juror ant of the Ishikari workflow, helping the judge ant.
${where}
Judge one task, ${t.id}. Its plan: ${env.state}/plans/${runOf(t.branch)}/${t.id}.md, a thin slice that names the
behaviours (B1...) and invariants (I1...) it covers. They are written out in the
product spec ${planDir}/product_spec.md. Read the merged code in
${scratchTree}, the code that will land on ${env.main}, and judge only this task:
does the code behave as each behaviour it covers says, and does each invariant it
covers hold? Score it 0 to 10 and list each gap as a short, concrete fix a worker
ant can build without questions, naming the id. Never change anything.${MAX_JURORS > 1 ? `
Other jurors read this folder at the same moment: never build or run the tests
in it. Judge by reading.` : ''}`,
    { label: `juror-ant:${round}:${t.id}`, phase: 'Upkeep', effort: EFFORT.juror, schema: SCORED },
  )
  const jury = async (round) => {
    if (merged.length < MIN_JURY) return []
    const out = []
    for (let k = 0; k < merged.length; k += MAX_JURORS) {
      const batch = merged.slice(k, k + MAX_JURORS)
      const got = []
      await parallel(batch.map((t, i) => async () => { got[i] = await juror(t, round) }))
      batch.forEach((t, i) => out.push({ id: t.id, report: got[i] && Number.isInteger(got[i].score) ? got[i] : null }))
    }
    return out
  }
  const judgeOnce = async (round) => {
    const reports = await jury(round)
    const juryText = reports.length ? `
Your jury has judged each task against its plan:
${reports.map(x => x.report ? `- ${x.id}: ${x.report.score}/10${(x.report.gaps || []).length ? `; gaps: ${x.report.gaps.join('; ')}` : ''}` : `- ${x.id}: no report (the juror died): judge this task yourself`).join('\n')}
Weigh their reports, check how the tasks fit together, then decide the run's score
yourself: it is not an average. Keep every gap you agree with.` : ''
    const j = await ant(
      `You are the judge ant of the Ishikari workflow.
${where}
Read the product spec ${planDir}/product_spec.md: the behaviours (B1...) and the
invariants (I1...) this run must deliver. Then read the merged code in
${scratchTree}, the code that will land on ${env.main}: the tasks (${names}) with the
janitor's cleanup on top if it landed.${juryText}
Judge one thing, id by id: does the code behave as each behaviour says, and does
each invariant hold? Score the whole run from 0 to 10, where 10 means every
behaviour is delivered, every invariant holds and no behaviour was added that the
spec does not have. The tech spec and the plans in that folder say how it was
meant to be built; they are not what you score. List each gap in "gaps" as a
short, concrete fix a worker ant can build without questions: the id, what is
missing or wrong, and in which file. Repeat in "bugs" each gap where the code
itself behaves wrongly; a missing or weak test is a gap, not a bug.
Never change anything.`,
      { label: `judge-ant:${round}`, phase: 'Upkeep', effort: EFFORT.judge,
        schema: SCORED },
    )
    return j && Number.isInteger(j.score) ? { score: Math.max(0, Math.min(10, j.score)), gaps: Array.isArray(j.gaps) ? j.gaps.map(String) : [], bugs: Array.isArray(j.bugs) ? j.bugs.map(String) : [] } : null
  }
  const judgeRun = async () => {
    if (upkeepStopped) return
    const first = await judgeOnce(1)
    if (!first) { verdict = { score: null, gaps: [], fixed: false, flagged: true, reason: 'the judge ant died' }; return }
    verdict = { score: first.score, gaps: first.gaps, fixed: false, flagged: first.score < PASS }
    const todo = first.score < PASS ? first.gaps : first.bugs
    if (!todo.length) return
    const BUILT = { type: 'object', properties: { status: { type: 'string', enum: ['built', 'stuck'] }, notes: { type: 'string' } }, required: ['status', 'notes'] }
    const b = await ant(
      `You are a worker ant of the Ishikari workflow, closing the judge ant's gaps.
${where}
The judge scored the run ${first.score}/10 against the product spec ${planDir}/product_spec.md. Gaps:
${todo.map(g => `- ${g}`).join('\n')}
Work only in the worktree ${fixTree} on branch ${fixBranch}. If either exists, remove
them first; then create it with \`git -C ${env.repo} worktree add -b ${fixBranch} ${fixTree} ${sha}\`.
Close the gaps so the code delivers the spec, keeping to the tech spec ${planDir}/tech_spec.md. Keep the tests passing (${tests} inside
${fixTree}). Commit on ${fixBranch} in small commits, no merge commits. Never touch
${scratch}, ${env.main} or the repo's main checkout. Return "stuck" if you cannot.`,
      { label: 'worker-ant:judge-fix', phase: 'Upkeep', effort: EFFORT.worker, schema: BUILT },
    )
    let bugs = ['the worker ant died']
    let landed = false
    if (b && b.status === 'built') {
      const c = await ant(
        `You are a detective ant of the Ishikari workflow, checking the fix for the judge ant's gaps.
${where}
Gaps:
${todo.map(g => `- ${g}`).join('\n')}
Code: ${fixTree}, branch ${fixBranch}, built on ${scratch}. Check that it closes the gaps
and breaks nothing, then ${tests} inside ${fixTree}. Return each problem in "bugs", or
an empty list. Never fix anything.
Only if you found no problem and the tests pass: \`git -C ${scratchTree} merge --ff-only ${fixBranch}\`,
set landed to true and return the new commit of ${scratch} as sha. If you found a
problem, or git refuses, leave ${scratch} alone and set landed to false.`,
        { label: 'detective-ant:judge-fix', phase: 'Upkeep', effort: EFFORT.detective,
          schema: { type: 'object', properties: {
            bugs: { type: 'array', items: { type: 'string' } },
            landed: { type: 'boolean', description: `true only if ${scratch} was fast-forwarded to the fix` },
            sha: { type: 'string' },
          }, required: ['bugs', 'landed'] } },
      )
      bugs = c && Array.isArray(c.bugs) ? c.bugs.map(String) : ['the detective ant died or gave no bug list']
      // The fix lands only through the detective's fast-forward: no bug, landed, commit named.
      if (!bugs.length && c.landed === true && isSha(c.sha)) landed = true
      // A clean "bugs found, nothing landed" left the scratch copy alone; anything else may have moved it.
      else if (!(c && bugs.length && c.landed === false)) await rewind('the judge fix')
      if (landed) sha = c.sha
    } else if (b) bugs = ['worker stuck: ' + b.notes]
    if (!landed) { fixKept = true; verdict.reason = bugs.join('; ') || 'could not fast-forward the scratch branch'; return }
    const second = await judgeOnce(2)
    verdict = second
      ? { score: second.score, gaps: second.gaps, fixed: true, flagged: second.score < PASS, first: first.score }
      : { ...verdict, fixed: true, reason: 'the judge ant died on its second look' }
  }
  await janitorChain()
  await judgeRun()
  await docsChain()
}

// ---- move main forward, clean up; the summary rows go in the log ----
phase('Main')
const entry = (t, event, who) => ({ run: runOf(t.branch), task: t.id, who, event })
const upkeep = [
  ...(docs ? [{ run: env.run, who: 'docs ant', event: docs.landed ? 'docs landed' : 'docs dropped', detail: docs.landed ? docs.title : `${docs.title}: ${docs.reason}` }] : []),
  ...(cleanup ? [{ run: env.run, who: 'janitor ant', event: cleanup.landed ? 'cleanup landed' : 'cleanup dropped', detail: cleanup.landed ? cleanup.title : `${cleanup.title}: ${cleanup.reason}` }] : []),
  ...(verdict ? [{ run: env.run, who: 'judge ant', event: verdict.flagged ? 'verdict flagged' : 'verdict', score: verdict.score == null ? '-' : verdict.score, detail: [...(verdict.fixed ? [`after one fix round (first score ${verdict.first == null ? '-' : verdict.first})`] : []), ...verdict.gaps, ...(verdict.reason ? [verdict.reason] : [])].join('\n') }] : []),
]
const rowsIf = moved => [
  ...merged.map(t => entry(t, moved ? 'done' : 'waiting', 'merger ant')),
  ...failed.map(t => entry(t, 'merge failed', 'merger ant')),
  ...waiting.map(t => entry(t, 'waiting', 'merger ant')),
  ...drop.map(t => entry(t, 'dropped', 'main session')),
  ...upkeep,
  ...(merged.length ? [{ run: env.run, who: 'finisher ant', event: moved ? 'main moved' : 'main not moved', detail: moved ? sha || '' : 'see the run report' }] : []),
]
const remove = [...merged.map(t => t.branch), `ishikari/${env.run}/_together`, scratch, ...(docsKept ? [] : [docsBranch]), ...(cleanKept ? [] : [cleanBranch]), ...(fixKept ? [] : [fixBranch])]
const FINISH = {
  type: 'object',
  properties: {
    moved: { type: 'boolean', description: `true if ${env.main} now points at the new commit` },
    reason: { type: 'string', description: 'if not moved, why' },
    check: {
      type: 'object',
      description: 'step 3 only',
      properties: { ran: { type: 'boolean' }, ok: { type: 'boolean' }, output: { type: 'string', description: 'last 20 lines' } },
      required: ['ran', 'ok', 'output'],
    },
  },
  required: ['moved', 'reason'],
}
const fin = await twice(() => ant(
  `You are Ishikari's finisher ant. Do these steps in order.
${where}
1. ${merged.length ? `Move ${env.main} forward to the checked commit ${sha}, only as a fast-forward.
   Always use that commit, never a branch name:
   - First run \`git -C ${env.repo} merge-base --is-ancestor ${sha} ${env.main}\`. If it succeeds,
     ${env.main} already holds the commit (an earlier try moved it): count it as moved
     and go on to step 2.
   - Find where ${env.main} is checked out: \`git -C ${env.repo} worktree list --porcelain\`.
   - If it is checked out in some worktree, run \`git -C <that worktree> merge --ff-only ${sha}\` there.
   - If it is checked out nowhere, run \`git -C ${env.repo} merge-base --is-ancestor ${env.main} ${sha}\`,
     and only if that succeeds, \`git -C ${env.repo} branch -f ${env.main} ${sha}\`.
   - If git refuses (main moved on, or local edits are in the way), stop moving: set
     moved to false and say why. Never reset, stash or discard anything.` : `Nothing was merged: leave ${env.main} alone (moved: false, reason: "nothing merged").`}
2. Only if step 1 moved ${env.main}, or nothing was merged: remove these worktrees and
   branches if they exist, with \`git -C ${env.repo} worktree remove --force <worktree>\`
   and \`git -C ${env.repo} branch -D <branch>\`:
${remove.map(b => `   - ${b} (worktree: ${treeOf(b)})`).join('\n')}
3. ${env.checkCommand && merged.length ? `Only if step 1 moved ${env.main}: build and check the real app. Run
   \`${env.checkCommand}\` from the checkout of ${env.main} (the worktree found in step 1,
   else ${env.repo}), with a 600 s timeout. Report ran, ok (exit 0) and the last 20
   lines of output in check. Never fix anything.` : 'No app check: report check as {ran: false, ok: false, output: ""}.'}`,
  { label: 'finisher-ant', phase: 'Main', effort: EFFORT.finisher, schema: FINISH },
))

const check = fin && fin.check ? fin.check : { ran: false, ok: false, output: '' }
const mainMoved = Boolean(merged.length && fin && fin.moved === true)
if (merged.length && !mainMoved) log(`main not moved: ${fin ? fin.reason : 'the finisher ant died twice'}`)
// Moved, or nothing merged: the rows say so; else the tasks still wait.
logNow(rowsIf(mainMoved || !merged.length))
return {
  stage: 'finish',
  mainMoved,
  reason: fin ? fin.reason : 'the finisher ant died twice',
  sha,
  merged: mainMoved ? merged.map(t => t.id) : [],
  notMoved: mainMoved ? [] : merged.map(t => ({ id: t.id, branch: t.branch, after: t.after || [] })),
  bugs,
  waiting,
  docs,
  cleanup,
  verdict,
  upkeepStopped,
  check,
  checkFixDone,
  checkFix: check.ran && !check.ok && !checkFixDone ? { task: 'check-fix', bug: String(check.output || '').trim() || 'the app check failed' } : null,
  checkFixRefused: Boolean(check.ran && !check.ok && checkFixDone),
  log: entries,
}
