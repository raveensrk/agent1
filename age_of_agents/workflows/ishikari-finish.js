export const meta = {
  name: 'ishikari-finish',
  description: 'Ishikari stage 3: merger ant merges approved tasks, then the janitor, librarian and philosopher ants run once',
  whenToUse: 'After the user approves tasks in their final review of ishikari-build.',
  phases: [
    { title: 'Merge', detail: 'one merger ant merges every approved task in order' },
    { title: 'Upkeep', detail: 'janitor, librarian and philosopher ants, in parallel' },
  ],
}

// args: {
//   repo: string,                      absolute repo path
//   approved: [{id, branch}],          tasks the user approved, in merge order
// }
// Returns { merged, bugs, cleanupPlan }.
// bugs feed the next ishikari-build run; cleanupPlan becomes a plan for it.

const MERGE = {
  type: 'object',
  properties: {
    results: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          merged: { type: 'boolean' },
          broke: { type: 'string', description: 'what broke on main, empty if nothing' },
        },
        required: ['id', 'merged', 'broke'],
      },
    },
  },
  required: ['results'],
}

const { repo, approved = [] } = args

phase('Merge')
const list = approved.map(t => `- ${t.id}: branch ${t.branch}`).join('\n')
const m = await agent(
  `You are the merger ant of the Ishikari workflow. Repo: ${repo}.
Merge these branches into main, one at a time, in this order:
${list}
After each merge, run the repo's tests on main. If the merge or the tests
fail, put main back as it was before that merge, report what broke, and go on
to the next branch.
If a later branch was built on top of a branch that failed (it contains that
branch's commits), skip it too and report "blocked" as what broke.
For each merged task: set its row in boards/bulletin.md to status "done",
then remove its worktree (.ishikari/worktrees/<id>) and delete its branch.
Last, commit any changes under boards/ with the message
"chore(boards): update after ishikari run". Commit nothing else.`,
  { label: 'merger-ant', phase: 'Merge', effort: 'low', schema: MERGE },
)

const results = m ? m.results : approved.map(t => ({ id: t.id, merged: false, broke: 'merger ant died' }))
const merged = results.filter(r => r.merged && !r.broke).map(r => r.id)
const bugs = results.filter(r => !r.merged || r.broke).map(r => {
  const t = approved.find(a => a.id === r.id) || { branch: `ishikari/${r.id}` }
  return { task: r.id, branch: t.branch, bug: `merge broke main: ${r.broke}` }
})

phase('Upkeep')
const [cleanupPlan] = merged.length ? await parallel([
  () => agent(
    `You are the janitor ant of the Ishikari workflow. Repo: ${repo}.
Find dead code, bloat and mess left by the tasks just merged (${merged.join(', ')}).
Only worker ants write code, so write a complete cleanup plan a worker ant can
build without questions, to ${repo}/.ishikari/plans/cleanup.md. Change no other
files. Return the plan, or "none" if nothing needs cleaning.`,
    { label: 'janitor-ant', phase: 'Upkeep' },
  ),
  () => agent(
    `You are the librarian ant of the Ishikari workflow. Repo: ${repo}.
Update the docs for the tasks just merged (${merged.join(', ')}). Change docs
only, and commit them.`,
    { label: 'librarian-ant', phase: 'Upkeep', effort: 'low' },
  ),
  // One philosopher looks at all the merged work together, once per run.
  () => agent(
    `You are the philosopher ant of the Ishikari workflow. Repo: ${repo}.
Question and critique the work just merged (${merged.join(', ')}) as a whole:
design, scope, missing cases, how the tasks fit together. Short, concrete
questions only. Add one row per critique to ${repo}/boards/critiques.md
(Target | Critique | Time), and commit only that file. The librarian ant may
commit at the same time: if git says the index is locked, wait a moment and
retry. Never block or change anything else.`,
    { label: 'philosopher-ant', phase: 'Upkeep' },
  ),
]) : ['none']

return { merged, bugs, cleanupPlan }
